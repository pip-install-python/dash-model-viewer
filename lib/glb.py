"""A dependency-free glTF 2.0 / GLB writer.

Both generative pages need to hand `<model-viewer>` a real `.glb`, and the
honest way to do that is to write one. GLB is a 12-byte header plus two
length-prefixed chunks — JSON, then a binary blob — so this is ~250 lines of
struct packing and no dependency at all. Reaching for a mesh library here would
add megabytes to the site to avoid arithmetic.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
No mesh reconstruction, no photogrammetry, no neural anything. The two callers
build geometry from *parameters* — primitives with transforms, or a height
field sampled from an image — and this module turns that into a file. The
language model's job is to choose the parameters; the geometry is deterministic
Python, inspectable and reproducible.

That split is the whole design. A model asked to emit vertices produces
plausible nonsense; a model asked "what shape is a lighthouse" produces
"a tall cylinder, a cone on top, a small emissive sphere" — which is a thing
code can build exactly.

SPEC POINTS THAT BITE
---------------------
* Every chunk must be padded to a 4-byte boundary — JSON with spaces (0x20),
  binary with zeros. An unpadded chunk fails to parse in three.js with an
  unhelpful error.
* `accessor.min` / `accessor.max` are REQUIRED on POSITION. Without them
  three.js cannot compute a bounding box, so `<model-viewer>` reports
  dimensions of zero and every camera-framing calculation collapses.
* glTF is right-handed, +Y up, -Z forward — the same convention
  `<model-viewer>`'s camera props use, so no axis conversion is needed.
"""

from __future__ import annotations

import json
import math
import struct
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["Mesh", "Material", "GLBBuilder", "box", "sphere", "cylinder", "cone", "torus", "plane"]

# Component types
_FLOAT = 5126
_UINT = 5125

# Buffer view targets
_ARRAY_BUFFER = 34962
_ELEMENT_ARRAY_BUFFER = 34963

Vec3 = Tuple[float, float, float]


class Material:
    """A glTF PBR metallic-roughness material."""

    def __init__(
        self,
        base_color: Sequence[float] = (0.8, 0.8, 0.8, 1.0),
        metallic: float = 0.0,
        roughness: float = 0.8,
        emissive: Sequence[float] = (0.0, 0.0, 0.0),
        name: str = "material",
        texture_png: Optional[bytes] = None,
        double_sided: bool = True,
    ):
        self.base_color = [float(c) for c in base_color]
        if len(self.base_color) == 3:
            self.base_color.append(1.0)
        self.metallic = float(metallic)
        self.roughness = float(roughness)
        self.emissive = [float(c) for c in emissive][:3]
        self.name = name
        self.texture_png = texture_png
        self.double_sided = double_sided


class Mesh:
    """Triangle geometry in object space, plus the transform placing it."""

    def __init__(
        self,
        positions: List[Vec3],
        indices: List[int],
        normals: Optional[List[Vec3]] = None,
        uvs: Optional[List[Tuple[float, float]]] = None,
        material: Optional[Material] = None,
        translation: Vec3 = (0.0, 0.0, 0.0),
        rotation_euler: Vec3 = (0.0, 0.0, 0.0),
        scale: Vec3 = (1.0, 1.0, 1.0),
        name: str = "mesh",
    ):
        self.positions = positions
        self.indices = indices
        self.normals = normals or _compute_normals(positions, indices)
        self.uvs = uvs
        self.material = material or Material()
        self.translation = tuple(float(v) for v in translation)
        self.rotation_euler = tuple(float(v) for v in rotation_euler)
        self.scale = tuple(float(v) for v in scale)
        self.name = name


def _compute_normals(positions: List[Vec3], indices: List[int]) -> List[Vec3]:
    """Area-weighted vertex normals. Smooth shading falls out of the sum."""
    acc = [[0.0, 0.0, 0.0] for _ in positions]
    for i in range(0, len(indices) - 2, 3):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]
        pa, pb, pc = positions[a], positions[b], positions[c]
        u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        n = (u[1] * v[2] - u[2] * v[1],
             u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0])
        for idx in (a, b, c):
            acc[idx][0] += n[0]
            acc[idx][1] += n[1]
            acc[idx][2] += n[2]
    out: List[Vec3] = []
    for n in acc:
        length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        out.append((n[0] / length, n[1] / length, n[2] / length))
    return out


def _euler_to_quat(rx: float, ry: float, rz: float) -> List[float]:
    """Degrees XYZ -> quaternion (x, y, z, w), glTF's node rotation form."""
    hx, hy, hz = (math.radians(a) / 2 for a in (rx, ry, rz))
    cx, sx = math.cos(hx), math.sin(hx)
    cy, sy = math.cos(hy), math.sin(hy)
    cz, sz = math.cos(hz), math.sin(hz)
    return [
        sx * cy * cz - cx * sy * sz,
        cx * sy * cz + sx * cy * sz,
        cx * cy * sz - sx * sy * cz,
        cx * cy * cz + sx * sy * sz,
    ]


class GLBBuilder:
    """Accumulates meshes, then emits one self-contained `.glb`."""

    def __init__(self) -> None:
        self._meshes: List[Mesh] = []

    def add(self, mesh: Mesh) -> "GLBBuilder":
        self._meshes.append(mesh)
        return self

    def extend(self, meshes: Sequence[Mesh]) -> "GLBBuilder":
        self._meshes.extend(meshes)
        return self

    # -- buffer plumbing ---------------------------------------------------

    def _pack(self) -> Tuple[bytes, Dict]:
        blob = bytearray()
        buffer_views: List[Dict] = []
        accessors: List[Dict] = []
        images: List[Dict] = []
        textures: List[Dict] = []
        materials: List[Dict] = []
        meshes: List[Dict] = []
        nodes: List[Dict] = []

        def align4() -> None:
            while len(blob) % 4:
                blob.append(0)

        def view(data: bytes, target: Optional[int] = None) -> int:
            align4()
            offset = len(blob)
            blob.extend(data)
            entry = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
            if target is not None:
                entry["target"] = target
            buffer_views.append(entry)
            return len(buffer_views) - 1

        def accessor(view_idx: int, ctype: int, count: int, atype: str,
                     minimum=None, maximum=None) -> int:
            entry = {
                "bufferView": view_idx,
                "componentType": ctype,
                "count": count,
                "type": atype,
            }
            if minimum is not None:
                entry["min"] = minimum
                entry["max"] = maximum
            accessors.append(entry)
            return len(accessors) - 1

        # Materials (and their textures) first — meshes reference them by index.
        material_index: Dict[int, int] = {}
        for mesh in self._meshes:
            key = id(mesh.material)
            if key in material_index:
                continue
            mat = mesh.material
            entry: Dict = {
                "name": mat.name,
                "doubleSided": mat.double_sided,
                "pbrMetallicRoughness": {
                    "baseColorFactor": mat.base_color,
                    "metallicFactor": mat.metallic,
                    "roughnessFactor": mat.roughness,
                },
            }
            if any(c > 0 for c in mat.emissive):
                entry["emissiveFactor"] = mat.emissive
            if mat.texture_png:
                img_view = view(mat.texture_png)
                images.append({"bufferView": img_view, "mimeType": "image/png"})
                textures.append({"source": len(images) - 1})
                entry["pbrMetallicRoughness"]["baseColorTexture"] = {
                    "index": len(textures) - 1
                }
            materials.append(entry)
            material_index[key] = len(materials) - 1

        for mesh in self._meshes:
            pos_bytes = b"".join(struct.pack("<3f", *p) for p in mesh.positions)
            nrm_bytes = b"".join(struct.pack("<3f", *n) for n in mesh.normals)
            idx_bytes = b"".join(struct.pack("<I", i) for i in mesh.indices)

            pos_view = view(pos_bytes, _ARRAY_BUFFER)
            nrm_view = view(nrm_bytes, _ARRAY_BUFFER)
            idx_view = view(idx_bytes, _ELEMENT_ARRAY_BUFFER)

            xs = [p[0] for p in mesh.positions]
            ys = [p[1] for p in mesh.positions]
            zs = [p[2] for p in mesh.positions]
            # REQUIRED on POSITION — without it three.js computes no bounding
            # box and model_info["dimensions"] comes back as zeros.
            pos_acc = accessor(pos_view, _FLOAT, len(mesh.positions), "VEC3",
                               [min(xs), min(ys), min(zs)],
                               [max(xs), max(ys), max(zs)])
            nrm_acc = accessor(nrm_view, _FLOAT, len(mesh.normals), "VEC3")
            idx_acc = accessor(idx_view, _UINT, len(mesh.indices), "SCALAR")

            attributes = {"POSITION": pos_acc, "NORMAL": nrm_acc}
            if mesh.uvs:
                uv_bytes = b"".join(struct.pack("<2f", *uv) for uv in mesh.uvs)
                uv_view = view(uv_bytes, _ARRAY_BUFFER)
                attributes["TEXCOORD_0"] = accessor(
                    uv_view, _FLOAT, len(mesh.uvs), "VEC2")

            meshes.append({
                "name": mesh.name,
                "primitives": [{
                    "attributes": attributes,
                    "indices": idx_acc,
                    "material": material_index[id(mesh.material)],
                }],
            })
            node: Dict = {"mesh": len(meshes) - 1, "name": mesh.name}
            if mesh.translation != (0.0, 0.0, 0.0):
                node["translation"] = list(mesh.translation)
            if mesh.rotation_euler != (0.0, 0.0, 0.0):
                node["rotation"] = _euler_to_quat(*mesh.rotation_euler)
            if mesh.scale != (1.0, 1.0, 1.0):
                node["scale"] = list(mesh.scale)
            nodes.append(node)

        gltf: Dict = {
            "asset": {"version": "2.0", "generator": "dash-model-viewer/lib.glb"},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes,
            "meshes": meshes,
            "materials": materials,
            "accessors": accessors,
            "bufferViews": buffer_views,
            "buffers": [{"byteLength": len(blob)}],
        }
        if images:
            gltf["images"] = images
            gltf["textures"] = textures
            gltf["samplers"] = [{"magFilter": 9729, "minFilter": 9987,
                                 "wrapS": 33071, "wrapT": 33071}]
            for tex in textures:
                tex["sampler"] = 0

        return bytes(blob), gltf

    def build(self) -> bytes:
        if not self._meshes:
            raise ValueError("nothing to build — add at least one mesh")

        blob, gltf = self._pack()
        json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")

        # Chunks are 4-byte aligned: JSON pads with spaces, BIN with zeros.
        json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
        blob += b"\x00" * ((4 - len(blob) % 4) % 4)

        total = 12 + 8 + len(json_bytes) + 8 + len(blob)
        out = bytearray()
        out += struct.pack("<III", 0x46546C67, 2, total)          # 'glTF', v2
        out += struct.pack("<II", len(json_bytes), 0x4E4F534A)    # 'JSON'
        out += json_bytes
        out += struct.pack("<II", len(blob), 0x004E4942)          # 'BIN\0'
        out += blob
        return bytes(out)


# --------------------------------------------------------------------------
# Primitives — the vocabulary a language model composes with
# --------------------------------------------------------------------------


def box(w: float = 1.0, h: float = 1.0, d: float = 1.0, **kw) -> Mesh:
    x, y, z = w / 2, h / 2, d / 2
    # Each face gets its own 4 vertices so normals stay flat at the edges.
    faces = [
        ([(-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)], (0, 0, 1)),
        ([(x, -y, -z), (-x, -y, -z), (-x, y, -z), (x, y, -z)], (0, 0, -1)),
        ([(x, -y, z), (x, -y, -z), (x, y, -z), (x, y, z)], (1, 0, 0)),
        ([(-x, -y, -z), (-x, -y, z), (-x, y, z), (-x, y, -z)], (-1, 0, 0)),
        ([(-x, y, z), (x, y, z), (x, y, -z), (-x, y, -z)], (0, 1, 0)),
        ([(-x, -y, -z), (x, -y, -z), (x, -y, z), (-x, -y, z)], (0, -1, 0)),
    ]
    positions: List[Vec3] = []
    normals: List[Vec3] = []
    uvs: List[Tuple[float, float]] = []
    indices: List[int] = []
    for corners, normal in faces:
        base = len(positions)
        positions.extend(corners)
        normals.extend([normal] * 4)
        uvs.extend([(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)])
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    return Mesh(positions, indices, normals, uvs, **kw)


def sphere(radius: float = 0.5, segments: int = 24, rings: int = 16, **kw) -> Mesh:
    positions: List[Vec3] = []
    uvs: List[Tuple[float, float]] = []
    indices: List[int] = []
    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        for seg in range(segments + 1):
            theta = 2 * math.pi * seg / segments
            positions.append((
                radius * math.sin(phi) * math.cos(theta),
                radius * math.cos(phi),
                radius * math.sin(phi) * math.sin(theta),
            ))
            uvs.append((seg / segments, ring / rings))
    for ring in range(rings):
        for seg in range(segments):
            a = ring * (segments + 1) + seg
            b = a + segments + 1
            indices.extend([a, b, a + 1, a + 1, b, b + 1])
    return Mesh(positions, indices, None, uvs, **kw)


def cylinder(radius: float = 0.5, height: float = 1.0, segments: int = 24,
             radius_top: Optional[float] = None, **kw) -> Mesh:
    rt = radius if radius_top is None else radius_top
    y = height / 2
    positions: List[Vec3] = []
    uvs: List[Tuple[float, float]] = []
    indices: List[int] = []

    for seg in range(segments + 1):
        theta = 2 * math.pi * seg / segments
        cos, sin = math.cos(theta), math.sin(theta)
        positions.append((radius * cos, -y, radius * sin))
        uvs.append((seg / segments, 1.0))
        positions.append((rt * cos, y, rt * sin))
        uvs.append((seg / segments, 0.0))
    for seg in range(segments):
        a = seg * 2
        indices.extend([a, a + 2, a + 1, a + 1, a + 2, a + 3])

    for sign, radius_cap, cap_y in ((1, rt, y), (-1, radius, -y)):
        if radius_cap <= 0:
            continue
        centre = len(positions)
        positions.append((0.0, cap_y, 0.0))
        uvs.append((0.5, 0.5))
        for seg in range(segments + 1):
            theta = 2 * math.pi * seg / segments
            positions.append((radius_cap * math.cos(theta), cap_y,
                              radius_cap * math.sin(theta)))
            uvs.append((0.5 + 0.5 * math.cos(theta), 0.5 + 0.5 * math.sin(theta)))
        for seg in range(segments):
            a = centre + 1 + seg
            if sign > 0:
                indices.extend([centre, a, a + 1])
            else:
                indices.extend([centre, a + 1, a])
    return Mesh(positions, indices, None, uvs, **kw)


def cone(radius: float = 0.5, height: float = 1.0, segments: int = 24, **kw) -> Mesh:
    return cylinder(radius=radius, height=height, segments=segments,
                    radius_top=0.0, **kw)


def torus(radius: float = 0.5, tube: float = 0.15, segments: int = 32,
          sides: int = 16, **kw) -> Mesh:
    positions: List[Vec3] = []
    uvs: List[Tuple[float, float]] = []
    indices: List[int] = []
    for i in range(segments + 1):
        u = 2 * math.pi * i / segments
        for j in range(sides + 1):
            v = 2 * math.pi * j / sides
            positions.append((
                (radius + tube * math.cos(v)) * math.cos(u),
                tube * math.sin(v),
                (radius + tube * math.cos(v)) * math.sin(u),
            ))
            uvs.append((i / segments, j / sides))
    for i in range(segments):
        for j in range(sides):
            a = i * (sides + 1) + j
            b = a + sides + 1
            indices.extend([a, b, a + 1, a + 1, b, b + 1])
    return Mesh(positions, indices, None, uvs, **kw)


def plane(w: float = 1.0, d: float = 1.0, **kw) -> Mesh:
    x, z = w / 2, d / 2
    positions = [(-x, 0.0, z), (x, 0.0, z), (x, 0.0, -z), (-x, 0.0, -z)]
    uvs = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    return Mesh(positions, [0, 1, 2, 0, 2, 3], [(0, 1, 0)] * 4, uvs, **kw)

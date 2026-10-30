# megascans_solaris_tool.py
# Tool rieng cho Houdini 22 + Solaris + Karma, khong phu thuoc Bridge plugin.
# Bridge chi dung de tai asset ve thu muc Downloaded.
# Cach dung trong Houdini Python Shell:
#   import sys
#   sys.path.append("C:/Users/USERD030/Documents/houdini22.0/scripts")
#   import megascans_solaris_tool as ms
#   ms.list_assets()
#   ms.assign_surface("/terrain", "rock_cliff_ui2ffgjlw", uv_repeat=4.0)
#   ms.import_3d("ullqbb1ga", lod=5)
#   ms.auto_assign()
#
# Quy uoc:
# - SOP layout: user layout object trong /obj nhu binh thuong.
# - Muon tool tu gan material cho 1 object, them spare parm "ms_asset"
#   vao object do (ms.add_ms_asset_parm("/obj/ten_object", "asset_id")),
#   roi chay ms.auto_assign(). Prim trong Solaris se la "/ten_object"
#   neu stage dang sceneimport /obj/* (nhu Crown).
# - Displacement mac dinh TAT, vi terrain lon bat displacement de crash.
#   Muon bat thi tu them node displacement vao material sau.

import hou
import json
import os
import re

LIBRARY_ROOT = "D:/CG_Library/Megascans_folder/Downloaded"
STAGE_PATH = "/stage"
MATERIALS_NODE = "ms_materials"
ASSIGN_NODE = "ms_assign_all"


def _sanitize(name):
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(name)).strip("_")


def _load_index():
    path = os.path.join(LIBRARY_ROOT, "assetsData.json")
    with open(path, encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
    return data


def list_assets(type_filter=None):
    """In danh sach asset da tai ve. type_filter: 'surface', '3d', 'atlas', None."""
    assets = _load_index()
    out = []
    for a in assets:
        t = a.get("type", "")
        if type_filter and t != type_filter:
            continue
        p = os.path.join(LIBRARY_ROOT, *a.get("path", []))
        out.append((a.get("id", ""), a.get("name", ""), t, p))
    for aid, name, t, p in out:
        print("%s | %s | %s | %s" % (aid, name, t, p))
    return out


def find_asset(query):
    """Tim asset theo id, ten folder, hoac ten hien thi (khong phan biet hoa thuong)."""
    q = str(query).strip().lower()
    assets = _load_index()
    for a in assets:
        if a.get("id", "").lower() == q:
            return a
    for a in assets:
        folder = a.get("path", [""])[-1].lower() if a.get("path") else ""
        if folder == q or folder.startswith(q):
            return a
    for a in assets:
        if q in a.get("name", "").lower():
            return a
    raise ValueError("Khong tim thay asset: %s" % query)


def asset_folder(asset):
    return os.path.join(LIBRARY_ROOT, *asset.get("path", []))


def asset_maps(asset, resolution="2K"):
    """Tra ve dict {Albedo, Normal, Roughness, AO, Displacement, Opacity, Metalness: filepath}.
    Uu tien dung resolution yeu cau, neu khong co thi lay resolution khac (2K truoc)."""
    folder = asset_folder(asset)
    files = os.listdir(folder) if os.path.isdir(folder) else []
    maps = {}
    wanted = ["Albedo", "Normal", "Roughness", "AO", "Displacement", "Opacity", "Metalness", "Translucency"]
    for m in wanted:
        # uu tien file khong co LOD, dung resolution yeu cau
        cands = []
        for fn in files:
            if ("_" + m + ".") in fn or ("_" + m + "_") in fn or fn.endswith("_" + m + ".jpg") or fn.endswith("_" + m + ".exr"):
                cands.append(fn)
        # chon theo thu tu resolution: yeu cau, 2K, 4K, 8K, 1K, bat ky
        order = [resolution, "2K", "4K", "8K", "1K"]
        chosen = None
        for res in order:
            for fn in cands:
                if ("_" + res + "_") in fn:
                    chosen = fn
                    break
            if chosen:
                break
        if not chosen and cands:
            # fallback: Normal LOD0 cho asset 3d
            for fn in cands:
                if "LOD0" in fn:
                    chosen = fn
                    break
            if not chosen:
                chosen = cands[0]
        if chosen:
            maps[m] = os.path.join(folder, chosen).replace("\\", "/")
    return maps


def _stage(stage_path=STAGE_PATH):
    stage = hou.node(stage_path)
    if stage is None:
        stage = hou.node("/").createNode("lopnet", stage_path.strip("/"))
    return stage


def _display_node(stage):
    try:
        d = stage.displayNode()
        if d is not None:
            return d
    except Exception:
        pass
    for child in stage.children():
        try:
            if child.isDisplayFlagSet():
                return child
        except Exception:
            continue
    return None


def _get_or_create_materials(stage):
    ml = hou.node(stage.path() + "/" + MATERIALS_NODE)
    if ml is None:
        ml = stage.createNode("materiallibrary", MATERIALS_NODE)
    return ml


def _get_or_create_assign(stage):
    am = hou.node(stage.path() + "/" + ASSIGN_NODE)
    if am is None:
        am = stage.createNode("assignmaterial", ASSIGN_NODE)
    return am


def _insert_before_display(stage, first_node, last_node):
    """Chen first_node -> last_node vao chain Solaris dung thu tu.
    - Neu stage da co karmarendersettings: chen truoc no, giu nguyen display.
    - Neu khong: chen SAU node dang display (thuong la sceneimport),
      roi chuyen display sang last_node. Chen truoc sceneimport la sai,
      vi sceneimport se ghi de len prim vua duoc gan material."""
    # neu da nam trong chain dung roi thi khong noi lai
    try:
        if last_node.input(0) == first_node:
            # kiem tra first_node co nam trong chain khong (co input hoac la node dau)
            return
    except Exception:
        pass
    karma_nodes = [c for c in stage.children()
                   if "karma" in c.type().name() or c.type().name() == "karmarendersettings"]
    if karma_nodes:
        disp = karma_nodes[0]
        prev = None
        try:
            prev = disp.input(0)
        except Exception:
            prev = None
        try:
            if prev is not None and prev not in (first_node, last_node):
                first_node.setInput(0, prev)
        except Exception:
            pass
        try:
            last_node.setInput(0, first_node)
        except Exception:
            pass
        try:
            disp.setInput(0, last_node)
        except Exception:
            pass
        return
    disp = _display_node(stage)
    if disp is None or disp in (first_node, last_node):
        try:
            last_node.setInput(0, first_node)
        except Exception:
            pass
        try:
            last_node.setDisplayFlag(True)
        except Exception:
            pass
        return
    try:
        first_node.setInput(0, disp)
    except Exception:
        pass
    try:
        last_node.setInput(0, first_node)
    except Exception:
        pass
    try:
        disp.setDisplayFlag(False)
        last_node.setDisplayFlag(True)
    except Exception:
        pass


def _connect(vop, input_name, src_node):
    names = vop.inputNames()
    if input_name not in names:
        return False
    idx = list(names).index(input_name)
    try:
        vop.setInput(idx, src_node)
        return True
    except Exception as e:
        print("  connect %s -> %s failed: %s" % (src_node.path(), input_name, e))
        return False


def _make_image(ml, name, filepath, signature=None):
    img = ml.createNode("mtlximage", name)
    try:
        img.parm("file").set(filepath)
    except Exception as e:
        print("  set file failed %s: %s" % (name, e))
    if signature:
        try:
            img.parm("signature").set(signature)
        except Exception:
            pass
    return img


def assign_surface(prim_path, asset_query, stage_path=STAGE_PATH, resolution="2K",
                   uv_repeat=1.0, use_ao=True, normal_scale=1.0):
    """Gan Surface cho 1 prim Solaris. Tra ve (material_prim_path, assign_node_path).
    Vi du: assign_surface("/terrain", "rock_cliff_ui2ffgjlw", uv_repeat=4.0)"""
    asset = find_asset(asset_query)
    maps = asset_maps(asset, resolution=resolution)
    if "Albedo" not in maps and "Normal" not in maps:
        raise ValueError("Asset %s khong co map Albedo/Normal trong %s" % (asset.get("name"), asset_folder(asset)))
    stage = _stage(stage_path)
    ml = _get_or_create_materials(stage)
    am = _get_or_create_assign(stage)
    mat_name = "ms_" + _sanitize(asset.get("id", asset.get("name", "asset")))
    # xoa surface cu cung ten VA cac image node kem theo de build lai sach
    for child in list(ml.children()):
        if child.name() == mat_name or child.name().startswith(mat_name + "_"):
            try:
                child.destroy()
            except Exception:
                pass
    surf = ml.createNode("mtlxstandard_surface", mat_name)
    try:
        surf.parm("metalness").set(0.0)
    except Exception:
        pass
    # UV repeat qua mtlxplace2d, dung chung cho moi image
    uv_node = None
    if uv_repeat and float(uv_repeat) != 1.0:
        try:
            uv_node = ml.createNode("mtlxplace2d", mat_name + "_uv")
            # place2d co parm scale dang vector2, thu set ca 2 dang
            for parm_name in ("scale",):
                try:
                    p = uv_node.parm(parm_name)
                    if p is not None:
                        p.set(float(uv_repeat))
                except Exception:
                    pass
            try:
                uv_node.parm("scale_vector2x").set(float(uv_repeat))
                uv_node.parm("scale_vector2y").set(float(uv_repeat))
            except Exception:
                pass
        except Exception as e:
            print("  place2d failed, bo qua uv_repeat: %s" % e)
            uv_node = None
    if "Albedo" in maps:
        albedo = _make_image(ml, mat_name + "_albedo", maps["Albedo"])
        if uv_node is not None:
            _connect(albedo, "texcoord", uv_node)
        if use_ao and "AO" in maps:
            ao = _make_image(ml, mat_name + "_ao", maps["AO"])
            if uv_node is not None:
                _connect(ao, "texcoord", uv_node)
            mul = ml.createNode("mtlxmultiply", mat_name + "_ao_mul")
            _connect(mul, "in1", albedo)
            _connect(mul, "in2", ao)
            _connect(surf, "base_color", mul)
        else:
            _connect(surf, "base_color", albedo)
    if "Normal" in maps:
        nimg = _make_image(ml, mat_name + "_normal", maps["Normal"])
        if uv_node is not None:
            _connect(nimg, "texcoord", uv_node)
        nm = ml.createNode("mtlxnormalmap", mat_name + "_nmap")
        try:
            nm.parm("scale").set(float(normal_scale))
        except Exception:
            pass
        _connect(nm, "in", nimg)
        _connect(surf, "normal", nm)
    if "Roughness" in maps:
        rimg = _make_image(ml, mat_name + "_rough", maps["Roughness"])
        if uv_node is not None:
            _connect(rimg, "texcoord", uv_node)
        _connect(surf, "specular_roughness", rimg)
    else:
        try:
            surf.parm("specular_roughness").set(0.9)
        except Exception:
            pass
    if "Metalness" in maps:
        mimg = _make_image(ml, mat_name + "_metal", maps["Metalness"])
        if uv_node is not None:
            _connect(mimg, "texcoord", uv_node)
        _connect(surf, "metalness", mimg)
    if "Opacity" in maps:
        oimg = _make_image(ml, mat_name + "_opacity", maps["Opacity"])
        if uv_node is not None:
            _connect(oimg, "texcoord", uv_node)
        _connect(surf, "opacity", oimg)
    # Displacement: chu dong KHONG gan, ghi ro trong docstring.
    mat_prim = "/materials/" + mat_name
    # gan vao assign node dung chung, them entry neu prim chua co
    try:
        n = int(am.parm("nummaterials").eval() or 1)
    except Exception:
        n = 1
    slot = None
    for i in range(1, n + 1):
        try:
            if am.parm("primpattern%d" % i).eval() == prim_path:
                slot = i
                break
        except Exception:
            continue
    if slot is None:
        # tim slot trong con, neu slot cuoi dang trong thi tang len
        try:
            last_pat = am.parm("primpattern%d" % n).eval()
        except Exception:
            last_pat = ""
        slot = n if not last_pat else n + 1
        if slot > n:
            try:
                am.parm("nummaterials").set(slot)
            except Exception:
                pass
    try:
        am.parm("primpattern%d" % slot).set(prim_path)
        am.parm("matspecpath%d" % slot).set(mat_prim)
        am.parm("enable%d" % slot).set(1)
    except Exception as e:
        print("  set assign slot failed: %s" % e)
    _insert_before_display(stage, ml, am)
    try:
        ml.layoutChildren()
    except Exception:
        pass
    print("OK: %s -> %s (assign %s, maps %s)" % (prim_path, mat_prim, am.path(), sorted(maps.keys())))
    return mat_prim, am.path()


def ensure_sceneimport(stage_path=STAGE_PATH, obj_pattern="/obj/*"):
    """Tao sceneimport neu stage chua co, de geometry SOP chay vao Solaris."""
    stage = _stage(stage_path)
    for child in stage.children():
        if child.type().name() == "sceneimport":
            print("Da co sceneimport: %s (objects=%s)" % (child.path(), child.parm("objects").eval() if child.parm("objects") else ""))
            return child.path()
    si = stage.createNode("sceneimport", "ms_sceneimport")
    try:
        si.parm("objects").set(obj_pattern)
    except Exception:
        pass
    for parm_name, val in (("importgeo", 1), ("importmats", 1)):
        try:
            si.parm(parm_name).set(val)
        except Exception:
            pass
    print("OK: tao sceneimport %s objects=%s" % (si.path(), obj_pattern))
    return si.path()


def import_3d(asset_query, obj_name=None, lod=0, stage_path=STAGE_PATH,
              resolution="2K", uv_repeat=1.0):
    """Import 1 asset 3d vao /obj dang File SOP (FBX), roi gan material Solaris.
    lod: chon LOD, mac dinh 0 (chi tiet nhat). Neu scene nang thi chon lod cao hon (vd 5)."""
    asset = find_asset(asset_query)
    if asset.get("type") != "3d":
        raise ValueError("Asset %s khong phai loai 3d (type=%s)" % (asset.get("name"), asset.get("type")))
    folder = asset_folder(asset)
    files = os.listdir(folder) if os.path.isdir(folder) else []
    fbx = None
    for fn in files:
        if fn.endswith("_LOD%d.fbx" % lod):
            fbx = fn
            break
    if fbx is None:
        fbxs = sorted([fn for fn in files if fn.endswith(".fbx")])
        if not fbxs:
            raise ValueError("Khong tim thay file FBX trong %s" % folder)
        fbx = fbxs[0]
    if obj_name is None:
        obj_name = _sanitize(asset.get("name", asset.get("id", "ms_3d")))
    obj = hou.node("/obj/" + obj_name)
    if obj is None:
        obj = hou.node("/obj").createNode("geo", obj_name)
    # tim hoac tao file node ben trong
    file_node = None
    for child in obj.children():
        if child.type().name() == "file":
            file_node = child
            break
    if file_node is None:
        file_node = obj.createNode("file", "file1")
    file_node.parm("file").set(os.path.join(folder, fbx).replace("\\", "/"))
    try:
        file_node.setDisplayFlag(True)
        file_node.setRenderFlag(True)
    except Exception:
        pass
    prim_path = "/" + obj_name
    mat_prim, assign_path = assign_surface(prim_path, asset_query, stage_path=stage_path,
                                           resolution=resolution, uv_repeat=uv_repeat)
    print("OK: 3d %s -> /obj/%s (FBX %s), material %s" % (asset.get("name"), obj_name, fbx, mat_prim))
    return obj.path(), mat_prim, assign_path


def add_ms_asset_parm(obj_path, asset_query):
    """Them spare parm ms_asset vao 1 object /obj, de auto_assign doc."""
    asset = find_asset(asset_query)
    node = hou.node(obj_path)
    if node is None:
        raise ValueError("Khong co node %s" % obj_path)
    if node.parm("ms_asset") is None:
        tmpl = hou.StringParmTemplate("ms_asset", "MS Asset", 1, default_value=(asset.get("id", ""),))
        try:
            node.addSpareParmTuple(tmpl)
        except Exception as e:
            print("addSpareParmTuple failed: %s" % e)
            return None
    node.parm("ms_asset").set(asset.get("id", ""))
    print("OK: %s ms_asset=%s (%s)" % (obj_path, asset.get("id"), asset.get("name")))
    return node.path()


def auto_assign(stage_path=STAGE_PATH, resolution="2K", uv_repeat=1.0):
    """Quet /obj, object nao co parm ms_asset thi gan material tuong ung.
    Prim mac dinh la /ten_object (dung khi stage sceneimport /obj/*)."""
    results = []
    obj_root = hou.node("/obj")
    if obj_root is None:
        return results
    for child in obj_root.children():
        p = child.parm("ms_asset")
        if p is None:
            continue
        asset_id = p.eval()
        if not asset_id:
            continue
        prim_path = "/" + child.name()
        try:
            mat_prim, assign_path = assign_surface(prim_path, asset_id, stage_path=stage_path,
                                                   resolution=resolution, uv_repeat=uv_repeat)
            results.append((child.path(), prim_path, mat_prim))
        except Exception as e:
            print("FAIL %s (%s): %s" % (child.path(), asset_id, e))
    print("auto_assign xong: %d object" % len(results))
    for r in results:
        print(" ", r)
    return results


def show_help():
    print("ms tool - Bridge chi de tai asset, tool nay gan MaterialX trong Solaris")
    print("  ms.list_assets() / ms.list_assets('surface') / ms.list_assets('3d')")
    print("  ms.assign_surface('/terrain', 'rock_cliff_ui2ffgjlw', uv_repeat=4.0)")
    print("  ms.ensure_sceneimport()  # neu stage chua import /obj/*")
    print("  ms.import_3d('ullqbb1ga', lod=5)")
    print("  ms.add_ms_asset_parm('/obj/ten_object', 'asset_id')")
    print("  ms.auto_assign()")

# Karma.py - patched into MSLiveLink 2026-10-30 by Muse, at user request.
# Adds Karma / MaterialX support to the Quixel Bridge Houdini plugin.
# Follows the exact pattern of Mantra.py: a creator class registered in
# MaterialsCreator, called by ImportSurface with (assetData, importParams,
# importOptions). importParams["materialPath"] is the container node:
#   - USD Surface: /stage/<AssetName> materiallibrary
#   - USD 3D: /stage/<AssetName> materiallibrary (via Import3D.createUsdMaterial)
#   - Normal: /mat, or /obj/<Asset>/materialNet for 3D
# Bridge components use lowercase types: albedo, diffuse, cavity, ao,
# normal, roughness, metalness, opacity, displacement, specular.
# Displacement is intentionally NOT connected: Mantra USD mode already
# forces disp scale 0, and full-terrain displacement is a crash risk
# (see Crown terrain work). User can add it manually later if needed.
import hou
from .MaterialsCreator import MaterialsCreator


def _connect(node, input_name, src):
    try:
        names = list(node.inputNames())
        if input_name not in names:
            return False
        node.setInput(names.index(input_name), src)
        return True
    except Exception as e:
        print("MSLiveLink Karma: connect failed %s -> %s: %s" % (src.path(), input_name, e))
        return False


def _image(container, name, path):
    img = container.createNode("mtlximage", name)
    try:
        img.parm("file").set(path.replace("\\", "/"))
    except Exception as e:
        print("MSLiveLink Karma: set file failed %s: %s" % (name, e))
    return img


class KarmaMaterialXMaterial:
    def createMaterial(self, assetData, importParams, importOptions):
        container = hou.node(importParams["materialPath"])
        asset_name = importParams["assetName"]
        surf = container.createNode("mtlxstandard_surface", asset_name)
        try:
            surf.parm("metalness").set(0.0)
            surf.parm("specular_roughness").set(0.9)
        except Exception:
            pass
        # Build component dict, prefer .jpg over .exr for colour maps.
        comps = {}
        for comp in assetData.get("components", []):
            t = str(comp.get("type", "")).lower()
            p = comp.get("path", "")
            if not t or not p:
                continue
            if t not in comps:
                comps[t] = p
            elif p.lower().endswith(".jpg") and not comps[t].lower().endswith(".jpg"):
                comps[t] = p
        albedo = comps.get("albedo") or comps.get("diffuse")
        if albedo:
            albedo_node = _image(container, asset_name + "_albedo", albedo)
            occ = comps.get("cavity") or comps.get("ao")
            if occ:
                occ_node = _image(container, asset_name + "_ao", occ)
                mul = container.createNode("mtlxmultiply", asset_name + "_ao_mul")
                _connect(mul, "in1", albedo_node)
                _connect(mul, "in2", occ_node)
                _connect(surf, "base_color", mul)
            else:
                _connect(surf, "base_color", albedo_node)
        if "normal" in comps:
            nimg = _image(container, asset_name + "_normal", comps["normal"])
            nmap = container.createNode("mtlxnormalmap", asset_name + "_nmap")
            try:
                nmap.parm("scale").set(1.0)
            except Exception:
                pass
            _connect(nmap, "in", nimg)
            _connect(surf, "normal", nmap)
        if "roughness" in comps:
            rimg = _image(container, asset_name + "_rough", comps["roughness"])
            _connect(surf, "specular_roughness", rimg)
        if "metalness" in comps:
            mimg = _image(container, asset_name + "_metal", comps["metalness"])
            _connect(surf, "metalness", mimg)
        if "opacity" in comps:
            oimg = _image(container, asset_name + "_opacity", comps["opacity"])
            _connect(surf, "opacity", oimg)
        # Displacement deliberately not connected (see header).
        return surf


def registerKarmaMaterials():
    creator = KarmaMaterialXMaterial()
    materialsCreator = MaterialsCreator()
    materialsCreator.registerMaterial("Karma", "MaterialX", creator.createMaterial)


registerKarmaMaterials()

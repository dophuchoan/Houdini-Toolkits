# Karma.py - patched into MSLiveLink 2026-10-30 by Muse, rewired 2026-11-02.
# Adds Karma / MaterialX support to the Quixel Bridge Houdini plugin.
# Follows the exact pattern of Mantra.py: a creator class registered in
# MaterialsCreator, called by ImportSurface with (assetData, importParams,
# importOptions). importParams["materialPath"] is the container node:
#   - USD Surface: /stage/<AssetName> materiallibrary
#   - USD 3D: /stage/<AssetName> materiallibrary (via Import3D.createUsdMaterial)
#   - Normal: /mat, or /obj/<Asset>/materialNet for 3D
# Bridge components use lowercase types: albedo, diffuse, cavity, ao,
# normal, roughness, metalness, opacity, displacement, specular.
# Normal + displacement wiring matches the user's live rewiring in
# Crown on 2026-11-02: mtlxnormal (space world) feeds the normalmap
# tangent input, normal/roughness/displacement images use filecolorspace
# Raw, and displacement is connected via mtlxdisplacement (scale 0.2).
# Previous version left tangent/normal unconnected and left displacement
# unconnected; that is the wiring the user corrected.
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


def _image(container, name, path, filecolorspace=None):
    img = container.createNode("mtlximage", name)
    try:
        img.parm("file").set(path.replace("\\", "/"))
    except Exception as e:
        print("MSLiveLink Karma: set file failed %s: %s" % (name, e))
    if filecolorspace:
        try:
            img.parm("filecolorspace").set(filecolorspace)
        except Exception:
            pass
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
            nimg = _image(container, asset_name + "_normal", comps["normal"], "Raw")
            nmap = container.createNode("mtlxnormalmap", asset_name + "_nmap")
            try:
                nmap.parm("scale").set(1.5)
            except Exception:
                pass
            # User rewiring 2026-11-02: world-space normal node feeds tangent.
            wnorm = container.createNode("mtlxnormal", asset_name + "_worldnormal")
            try:
                wnorm.parm("space").set("world")
            except Exception:
                pass
            _connect(nmap, "in", nimg)
            _connect(nmap, "tangent", wnorm)
            _connect(surf, "normal", nmap)
        if "roughness" in comps:
            rimg = _image(container, asset_name + "_rough", comps["roughness"], "Raw")
            _connect(surf, "specular_roughness", rimg)
        if "metalness" in comps:
            mimg = _image(container, asset_name + "_metal", comps["metalness"])
            _connect(surf, "metalness", mimg)
        if "opacity" in comps:
            oimg = _image(container, asset_name + "_opacity", comps["opacity"])
            _connect(surf, "opacity", oimg)
        if "displacement" in comps:
            dimg = _image(container, asset_name + "_disp", comps["displacement"], "Raw")
            disp = container.createNode("mtlxdisplacement", asset_name + "_displacement")
            try:
                disp.parm("scale").set(0.2)
            except Exception:
                pass
            _connect(disp, "displacement", dimg)
        return surf


def registerKarmaMaterials():
    creator = KarmaMaterialXMaterial()
    materialsCreator = MaterialsCreator()
    materialsCreator.registerMaterial("Karma", "MaterialX", creator.createMaterial)


registerKarmaMaterials()

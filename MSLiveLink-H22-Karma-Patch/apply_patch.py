"""Apply the MSLiveLink Houdini 22 Karma/MaterialX patch to a Bridge-installed plugin.

Usage (run with any Python, inside or outside Houdini - it only edits text files):
    python apply_patch.py "D:/CG_Library/Megascans_folder/support/plugins/houdini/4.6/MSLiveLink"

What it does:
  1. Copies MaterialsSetup/Karma.py (bundled in this repo, next to this script)
     into <plugin>/scripts/python/MSPlugin/MaterialsSetup/Karma.py
  2. Applies the exact string replacements below to AssetData.py, OptionsUI.py,
     ImportSurface.py and Import3D.py. Each replacement must match exactly once,
     otherwise the script aborts without writing that file.
  3. Deletes __pycache__ folders under the plugin so Houdini recompiles fresh.

After running: restart Houdini completely, then verify in the Megascans plugin
window that Renderer includes Karma, Material Type includes MaterialX, the
"Import Assets on USD Stage" checkbox is clickable, and USD Material can be
set to Karma.

Do NOT press Bridge Download/Install Plugin again after patching, or Bridge
will overwrite the patched files with the originals. If that happens, just
run this script again.

This repo deliberately does NOT contain Quixel's original plugin files or
any Megascans assets. Install the plugin normally through Bridge first,
then run this patch on top of it.
"""
import os
import shutil
import sys

PATCHES = [
    # (relative path, old text, new text)
    (
        "scripts/python/MSPlugin/Utilities/AssetData.py",
        '    USDSupportedVersions = ["18", "19"]',
        '    USDSupportedVersions = ["18", "19", "20", "21", "22"]  # patched 2026-10-30: H22 Karma/MaterialX integration',
    ),
    (
        "scripts/python/MSPlugin/OptionsUI.py",
        '        self.supportedRenderers = ["Mantra", "Arnold", "Octane", "Redshift", "Renderman"]',
        '        self.supportedRenderers = ["Mantra", "Arnold", "Octane", "Redshift", "Renderman", "Karma"]',
    ),
    (
        "scripts/python/MSPlugin/OptionsUI.py",
        '        self.usdCheck.setToolTip("Import and setup assets in Solaris in Houdini 18.")',
        '        self.usdCheck.setToolTip("Import and setup assets in Solaris in Houdini 18+.")',
    ),
    (
        "scripts/python/MSPlugin/OptionsUI.py",
        '            if renderer == "Mantra":\n                rendererList.append(renderer)\n',
        '            if renderer == "Mantra":\n                rendererList.append(renderer)\n\n            if renderer == "Karma":\n                rendererList.append(renderer)\n',
    ),
    (
        "scripts/python/MSPlugin/AssetImporters/ImportSurface.py",
        '            usdMaterials = {"Mantra" : "Principled Shader", "Renderman" : "Pixar Surface", "Arnold" : "Standard Surface"}',
        '            usdMaterials = {"Mantra" : "Principled Shader", "Renderman" : "Pixar Surface", "Arnold" : "Standard Surface", "Karma" : "MaterialX"}',
    ),
    (
        "scripts/python/MSPlugin/AssetImporters/ImportSurface.py",
        '            if usdRendererType == "Karma":\n                usdRendererType = "Mantra"\n',
        '            # patched 2026-10-30: Karma now uses its own MaterialX creator, no longer remapped to Mantra.\n',
    ),
    (
        # importScatterUSD in Import3D.py
        "scripts/python/MSPlugin/AssetImporters/Import3D.py",
        '        materialReference = primitiveConfigNode.createOutputNode("reference")\n'
        '        materialPrimPath =   primitiveBasePath + "/Material"\n'
        '        materialReference.parm("primpath").set(materialPrimPath)\n'
        '        materialReference.parm("reftype").set("inputref")\n'
        '\n'
        '        assignMaterial = materialReference.createOutputNode("assignmaterial")\n'
        '        # assignMaterial.parm("primpattern1").set(primitiveBasePath + "/*")\n'
        '        assignMaterial.parm("primpattern1").set(primitiveBasePath + "/*")\n'
        '        assignMaterial.parm("matspecpath1").set(materialPrimPath + "/" + assetMaterial.name())\n'
        '        materialReference.setInput(1, matConfigNode)\n',
        '        # Patched 2026-10-30 for Houdini 22: same broken "inputref"\n'
        '        # reference as in usdAssetSetup, replaced by a merge (see above).\n'
        '        materialMerge = primitiveConfigNode.createOutputNode("merge")\n'
        '        materialMerge.setInput(1, matConfigNode)\n'
        '        _containerPath = usdMaterialContainer.parm("containerpath").eval()\n'
        '        if not _containerPath.endswith("/"):\n'
        '            _containerPath += "/"\n'
        '        assignMaterial = materialMerge.createOutputNode("assignmaterial")\n'
        '        # assignMaterial.parm("primpattern1").set(primitiveBasePath + "/*")\n'
        '        assignMaterial.parm("primpattern1").set(primitiveBasePath + "/*")\n'
        '        assignMaterial.parm("matspecpath1").set(_containerPath + assetMaterial.name())\n',
    ),
    (
        # usdAssetSetup in Import3D.py
        "scripts/python/MSPlugin/AssetImporters/Import3D.py",
        '        materialReference = primitiveConfigNode.createOutputNode("reference")\n'
        '        materialPrimPath =   primitiveBasePath + "/Material"\n'
        '        materialReference.parm("primpath").set(materialPrimPath)\n'
        '        materialReference.parm("reftype").set("inputref")\n'
        '\n'
        '        matConfigNode = usdMaterialContainer.createOutputNode("configurelayer")\n'
        '\n'
        '        assignMaterial = materialReference.createOutputNode("assignmaterial")\n'
        '        assignMaterial.parm("primpattern1").set(primitivePath)\n'
        '        assignMaterial.parm("matspecpath1").set(materialPrimPath + "/" + assetMaterial.name())\n'
        '        materialReference.setInput(1, matConfigNode)\n',
        '        # Patched 2026-10-30 for Houdini 22: the old reference node with\n'
        '        # reftype "inputref" fails on H22 ("Failed adding file reference:\n'
        '        # anon:...LOP:rootlayer, ancestor primitive is inactive"), leaving\n'
        '        # the /Megascans/.../Material prim empty, so the assignmaterial\n'
        '        # below could not find its material. Merge the geometry stage and\n'
        '        # the materiallibrary stage directly instead; the materiallibrary\n'
        '        # already creates its material at /materials/<assetName>.\n'
        '        matConfigNode = usdMaterialContainer.createOutputNode("configurelayer")\n'
        '        materialMerge = primitiveConfigNode.createOutputNode("merge")\n'
        '        materialMerge.setInput(1, matConfigNode)\n'
        '        _containerPath = usdMaterialContainer.parm("containerpath").eval()\n'
        '        if not _containerPath.endswith("/"):\n'
        '            _containerPath += "/"\n'
        '        assignMaterial = materialMerge.createOutputNode("assignmaterial")\n'
        '        assignMaterial.parm("primpattern1").set(primitivePath)\n'
        '        assignMaterial.parm("matspecpath1").set(_containerPath + assetMaterial.name())\n',
    ),
]


def main():
    if len(sys.argv) < 2:
        print("Usage: python apply_patch.py <path-to-MSLiveLink-plugin-folder>")
        return 1
    plugin = sys.argv[1]
    if not os.path.isdir(os.path.join(plugin, "scripts", "python", "MSPlugin")):
        print("Not an MSLiveLink plugin folder:", plugin)
        return 1
    # 1. Copy Karma.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    karma_src = os.path.join(script_dir, "MaterialsSetup", "Karma.py")
    karma_dst = os.path.join(plugin, "scripts", "python", "MSPlugin", "MaterialsSetup", "Karma.py")
    shutil.copyfile(karma_src, karma_dst)
    print("Copied Karma.py ->", karma_dst)
    # 2. Apply replacements, grouped per file so a file is written once
    by_file = {}
    for rel, old, new in PATCHES:
        by_file.setdefault(rel, []).append((old, new))
    for rel, reps in by_file.items():
        path = os.path.join(plugin, rel)
        text = open(path, encoding="utf-8", errors="ignore").read()
        for old, new in reps:
            count = text.count(old)
            if count != 1:
                print("ABORT: expected exactly 1 match in %s, found %d for:\n%s" % (rel, count, old[:120]))
                return 1
            text = text.replace(old, new)
        open(path, "w", encoding="utf-8").write(text)
        print("Patched", rel, "(%d replacements)" % len(reps))
    # 3. Clean __pycache__
    for root, dirs, _files in os.walk(plugin):
        if "__pycache__" in dirs:
            shutil.rmtree(os.path.join(root, "__pycache__"), ignore_errors=True)
            dirs.remove("__pycache__")
    print("Cleaned __pycache__. Done - restart Houdini to load the patched plugin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

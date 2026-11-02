# MSLiveLink — Karma / MaterialX patch cho Houdini 22

Patch cho plugin **MSLiveLink 4.6** của Quixel Bridge, để xuất asset Megascans
ra **Solaris / Karma với MaterialX** trên Houdini 22. Được làm và kiểm chứng
ngày 2026-10-30 trên Houdini 22.0.368, và cập nhật dây normal/displacement
ngày 2026-11-02 theo đúng cách nối lại trong scene Crown (xem dưới).

## Patch này làm gì

- Thêm **Renderer: Karma** và **Material Type: MaterialX** vào cửa sổ plugin.
  Material mới (`MaterialsSetup/Karma.py`) tạo `mtlxstandard_surface` với
  albedo (nhân với AO/cavity nếu có), normal qua `mtlxnormalmap`,
  roughness, metalness, opacity.
- **Cập nhật 2026-11-02 — dây normal/displacement nối lại theo scene Crown:**
  ảnh normal vào `in` của `mtlxnormalmap`, node `mtlxnormal` (space world)
  vào `tangent` của `mtlxnormalmap`, Scale của nmap là 1.5, ảnh
  normal/roughness/displacement dùng `filecolorspace` Raw, và displacement
  được nối qua `mtlxdisplacement` (Scale 0.2) thay vì bỏ trống như bản
  2026-10-30. Lưu ý: trong import dạng flat materiallibrary, node
  displacement được tạo đúng dây vào nhưng không có cổng
  `displacement_output` như trong subnet, nên cần kiểm tra lại phần
  displacement khi export thử.
- Mở khóa **Import Assets on USD Stage** trên Houdini 22: trước đây plugin
  chỉ cho phép USD ở version 18, 19 nên checkbox bị khóa trên H22.
- Sửa USD Material: chọn Karma thì dùng đúng MaterialX, không bị remap
  ngược về Mantra như bản gốc.
- Sửa lỗi USD 3D trên H22: node `reference` kiểu `inputref` trong
  `usdAssetSetup` và `importScatterUSD` hay lỗi, để lại prim Material rỗng
  nên `assignmaterial` không tìm thấy material. Patch thay nó bằng node
  `merge` gộp stage geometry với stage materiallibrary, và trỏ
  `assignmaterial` đúng tới `/materials/<tên asset>`.

## Repo này KHÔNG chứa gì

- **Không chứa code gốc của Quixel** và **không chứa asset Megascans**.
  Bạn phải cài plugin gốc qua Bridge trước, rồi chạy patch này đè lên.
- Asset (texture, FBX) vẫn nằm trong thư mục `Downloaded` của Bridge,
  phải tự tải hoặc copy riêng.

## Cách cài

1. Trong Bridge: Edit > Export Settings, Export Target = Houdini,
   Download Plugin rồi Install Plugin. Đóng Houdini trước khi cài plugin.
2. Copy thư mục plugin đã cài, ví dụ
   `<Library>/support/plugins/houdini/4.6/MSLiveLink`, để dành bản gốc.
3. Chạy script patch, trỏ tới thư mục plugin đó:
   ```
   python apply_patch.py "D:/CG_Library/Megascans_folder/support/plugins/houdini/4.6/MSLiveLink"
   ```
   Script sẽ copy `MaterialsSetup/Karma.py` vào plugin, áp các đoạn sửa
   vào 4 file (`AssetData.py`, `OptionsUI.py`, `ImportSurface.py`,
   `Import3D.py`), mỗi đoạn phải khớp đúng 1 lần nếu không sẽ dừng lại,
   rồi xóa `__pycache__` để Houdini biên dịch lại.
4. Copy file `packages/MSLiveLink.json` vào
   `Documents/houdini22.0/packages/MSLiveLink.json`, rồi **sửa đường dẫn
   bên trong file** cho đúng đường dẫn plugin ở máy bạn. Nếu Houdini khác
   version thì đổi tên thư mục packages cho đúng version đó.
5. Đóng hẳn Houdini rồi mở lại.
6. Kiểm tra: menu Megascans mở được, Renderer có Karma, Material Type có
   MaterialX, tick được Import Assets on USD Stage, USD Material chọn
   được Karma.

## Lưu ý

- Sau khi patch xong, **đừng bấm lại Download/Install Plugin trong Bridge**,
  vì Bridge sẽ ghi đè bản patch bằng bản gốc. Nếu lỡ bấm, chạy lại
  `apply_patch.py` một lần nữa là xong.
- Asset 3D xuất kiểu USD sẽ tự tạo subnet trong `/stage` gồm geometry,
  materiallibrary và assignmaterial, không cần sceneimport tay. Asset
  Surface thì chỉ tạo material, bạn cần `assignmaterial` tay tới prim
  cần gán (ví dụ `/terrain`).
- Thư mục `fallback/` chứa tool Solaris rời dự phòng
  (`megascans_solaris_tool.py`), chỉ dùng khi không muốn dùng MSLiveLink.

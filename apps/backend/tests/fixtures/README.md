# Test fixture'ları

- `legacy_presentation.ppt` — gerçek eski ikili PowerPoint 97-2003 (`.ppt`) dosyası; 2
  slayt, başlık metni + konuşmacı notu içerir. `ppt2pptx` projesinin kendi test
  paketinden alındı (MIT lisans): https://github.com/HuiTurn/ppt2pptx —
  `tests/fixtures/visual_minimal.ppt`. `.ppt` yüklemesinin `ppt2pptx` ile `.pptx`'e
  çevrilip doğru şekilde okunduğunu doğrulamak için kullanılır (sentetik/programatik
  olarak geçerli bir `.ppt` CFB/OLE ikili dosyası üretmek pratik değil).

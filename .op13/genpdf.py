import sys, pymupdf

SENT = ("Bilissel gelisim kuramina gore cocuk cevresiyle etkilesim kurarak sema olusturur. "
        "Ozumleme ve uyumsama sureclerinin dengesi dengeleme olarak adlandirilir. "
        "Duyusal motor donemde nesne surekliligi kazanilir ve tekrarli eylemler sema haline gelir. ")

def build(path, pages, chars_per_page):
    doc = pymupdf.open()
    body = (SENT * 200)[:chars_per_page]
    for i in range(1, pages + 1):
        page = doc.new_page()
        text = f"Sayfa {i} - Bolum {((i - 1) // 5) + 1}\n" + body
        page.insert_textbox(pymupdf.Rect(40, 40, 560, 800), text, fontsize=7, fontname="helv")
    doc.save(path)
    doc.close()

if __name__ == "__main__":
    build(".op13/test_3p.pdf", 3, 2200)
    build(".op13/test_20p.pdf", 20, 2200)
    build(".op13/test_70p.pdf", 70, 2200)
    print("built")

"""Build the Indonesian end-user tutorial PDF for the Tryon Bot.

Run with:  python scripts/build_tutorial_pdf.py [output.pdf]
The PDF is reproducible from this script, so we don't commit the generated
file (see .gitignore). CI / docs will run the script when needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
)
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "freepik_tryon_bot" / "assets"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title",
        parent=base["Title"],
        fontSize=24,
        textColor=colors.HexColor("#5d3b00"),
        leading=28,
        alignment=1,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=base["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#5d3b00"),
        leading=20,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=base["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#7a5800"),
        leading=16,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body",
        parent=base["BodyText"],
        fontSize=10.5,
        leading=14,
        spaceAfter=4,
    )
    small = ParagraphStyle(
        "Small",
        parent=base["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#7a5800"),
    )
    return {"title": title, "h1": h1, "h2": h2, "body": body, "small": small}


def build(output: Path) -> None:
    s = _styles()
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Tutorial Tryon Bot",
        author="Aksara Strategy",
    )

    flow = []
    flow.append(Paragraph("Tutorial Penggunaan Bot", s["title"]))
    flow.append(Paragraph("Mannequin Tryon &amp; Hanger", s["h2"]))
    flow.append(Spacer(1, 0.6 * cm))
    flow.append(
        Paragraph(
            "Panduan singkat berbahasa Indonesia untuk user akhir bot Telegram. "
            "Bot mengganti pakaian pada gambar referensi dengan outfit yang Anda upload, "
            "dan mempertahankan latar belakang, pencahayaan, sudut kamera, dan nuansa "
            "yang konsisten.",
            s["body"],
        )
    )
    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph("By : Aksara Strategy", s["small"]))
    flow.append(Spacer(1, 0.6 * cm))

    flow.append(Paragraph("1. Akses awal", s["h1"]))
    flow.append(
        Paragraph(
            "Buka bot di Telegram, lalu ketik <b>/start</b>. Bot akan menampilkan "
            "menu utama dengan 4 tombol: <b>Mannequin Tryon</b>, <b>Hanger</b>, "
            "<b>Saldo Token</b>, dan <b>Bantuan</b>.",
            s["body"],
        )
    )
    flow.append(
        Paragraph(
            "Cek saldo token kapan saja dengan menekan tombol <b>💎 Saldo Token</b> "
            "atau ketik <b>/saldo</b>. Setiap gambar yang berhasil dikirim memotong "
            "1 token dari saldo Anda.",
            s["body"],
        )
    )
    flow.append(Spacer(1, 0.4 * cm))

    flow.append(Paragraph("2. Mannequin Tryon", s["h1"]))
    flow.append(
        Paragraph(
            "Bot menyediakan <b>2 gambar referensi mannequin</b> (mannequin di depan "
            "cermin tinggi). Anda hanya perlu mengirim <b>1 foto outfit</b>. Bot akan "
            "menerapkan outfit tersebut ke kedua gambar referensi tanpa mengubah "
            "background, pose, atau bagian cermin.",
            s["body"],
        )
    )
    flow.append(Paragraph("Langkah:", s["h2"]))
    flow.append(
        Paragraph(
            "1. Tekan <b>👗 Mannequin Tryon</b> di menu utama.<br/>"
            "2. Kirim 1 foto outfit (JPG/PNG/WebP, polos atau flat-lay paling baik).<br/>"
            "3. Tunggu progress generate (akan muncul progress bar 0–100%).<br/>"
            "4. Bot mengirim 2 gambar hasil + sisa token.",
            s["body"],
        )
    )
    if (ASSETS / "mannequin_1.jpg").exists():
        try:
            tab = Table(
                [
                    [
                        RLImage(str(ASSETS / "mannequin_1.jpg"), width=7 * cm, height=9 * cm),
                        RLImage(str(ASSETS / "mannequin_2.jpg"), width=7 * cm, height=9 * cm),
                    ]
                ],
                colWidths=[7.5 * cm, 7.5 * cm],
            )
            tab.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            flow.append(Spacer(1, 0.3 * cm))
            flow.append(tab)
            flow.append(Spacer(1, 0.2 * cm))
            flow.append(
                Paragraph(
                    "<i>2 gambar referensi yang akan dipakai bot untuk Mannequin Tryon.</i>",
                    s["small"],
                )
            )
        except Exception:  # noqa: BLE001
            pass

    flow.append(PageBreak())

    flow.append(Paragraph("3. Hanger", s["h1"]))
    flow.append(
        Paragraph(
            "Bot menyediakan <b>2 gambar referensi hanger</b> (rak gantungan). Anda "
            "memilih <b>jumlah outfit</b> (1–5) lalu mengirim foto outfit satu per satu. "
            "Urutan upload menentukan posisi kiri-ke-kanan di rak gantungan.",
            s["body"],
        )
    )
    flow.append(Paragraph("Langkah:", s["h2"]))
    flow.append(
        Paragraph(
            "1. Tekan <b>🧥 Hanger</b> di menu utama.<br/>"
            "2. Pilih jumlah outfit yang akan digantung (tombol 1–5).<br/>"
            "3. Kirim foto outfit ke-1, ke-2, … sampai foto terakhir.<br/>"
            "4. Tunggu progress generate.<br/>"
            "5. Bot mengirim 2 gambar hasil + sisa token.",
            s["body"],
        )
    )
    if (ASSETS / "hanger_1.jpg").exists():
        try:
            tab = Table(
                [
                    [
                        RLImage(str(ASSETS / "hanger_1.jpg"), width=7 * cm, height=7 * cm),
                        RLImage(str(ASSETS / "hanger_2.jpg"), width=7 * cm, height=7 * cm),
                    ]
                ],
                colWidths=[7.5 * cm, 7.5 * cm],
            )
            tab.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            flow.append(Spacer(1, 0.3 * cm))
            flow.append(tab)
            flow.append(Spacer(1, 0.2 * cm))
            flow.append(
                Paragraph(
                    "<i>2 gambar referensi rak gantungan untuk fitur Hanger.</i>",
                    s["small"],
                )
            )
        except Exception:  # noqa: BLE001
            pass

    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph("4. Saldo &amp; Top-up Token", s["h1"]))
    flow.append(
        Paragraph(
            "Setiap gambar yang berhasil dikirim memotong 1 token. Karena tiap "
            "fitur menghasilkan 2 gambar, sekali generate normalnya memotong "
            "2 token. Apabila gambar gagal terkirim, token tidak dipotong.",
            s["body"],
        )
    )
    flow.append(
        Paragraph(
            "Saat saldo turun di angka <b>10 atau kurang</b>, bot otomatis "
            "menampilkan peringatan: <i>“Token sisa X segera hubungi admin untuk "
            "Top-up Token”</i>. Hubungi admin untuk menambah token Anda.",
            s["body"],
        )
    )

    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph("5. Tips kualitas hasil", s["h1"]))
    flow.append(
        Paragraph(
            "• Foto outfit dengan latar polos atau flat-lay menghasilkan hasil paling akurat.<br/>"
            "• Pastikan seluruh pakaian terlihat (lengan, leher, panjang baju).<br/>"
            "• Hindari foto outfit dipakai orang dengan banyak pose; bot fokus "
            "menyalin baju, bukan tubuh model.<br/>"
            "• Untuk Hanger, urutan upload = urutan kiri-ke-kanan di rak gantungan.",
            s["body"],
        )
    )

    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph("6. Perintah cepat", s["h1"]))
    cmds = [
        ["<b>Perintah</b>", "<b>Fungsi</b>"],
        ["/start", "Buka menu utama, tampilkan saldo token."],
        ["/menu", "Tampilkan ulang menu utama."],
        ["/saldo", "Cek saldo token saat ini."],
        ["/myid", "Tampilkan user_id Anda (untuk diberikan ke admin)."],
        ["/help", "Tutorial singkat."],
        ["/batal", "Membatalkan flow yang sedang berjalan."],
    ]
    table = Table(
        [[Paragraph(c, s["body"]) for c in row] for row in cmds],
        colWidths=[4 * cm, 12 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5e9c8")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#b08a3a")),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#d8c595")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    flow.append(table)

    flow.append(Spacer(1, 0.6 * cm))
    flow.append(Paragraph("By : Aksara Strategy", s["small"]))

    doc.build(flow)


def main() -> None:
    if len(sys.argv) > 1:
        output = Path(sys.argv[1])
    else:
        output = REPO_ROOT / "docs" / "tutorial_tryon_bot.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    build(output)
    print(f"Wrote {output} ({output.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

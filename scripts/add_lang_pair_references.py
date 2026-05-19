"""Add fr, th, ms reference translations to every annotation in data/annotations/.

These references are written for the v0.1 sample dataset to make
LayoutTranslateBench cover the languages most relevant to the EU
(France) and Southeast Asia (Thailand, Malaysia) markets that real
buyers care about — including markets where commercial tools like
DeepL Documents currently have zero coverage (th, ms).

Translations are author-curated for the v0.1 sample. They are NOT
certified human-translator outputs; v0.2 will replace them with
certified references via a paid translator partner.

Idempotent: re-running is safe; existing keys are preserved.

Run from repo root:
    python scripts/add_lang_pair_references.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# (doc_id, region_id) -> {lang_pair: reference}
REFS: dict[tuple[str, str], dict[str, str]] = {
    # ---------- doc_001 — Certificate of Birth ----------
    ("doc_001", "r1"): {
        "en-fr": "Acte de Naissance",
        "en-th": "สูติบัตร",
        "en-ms": "Sijil Kelahiran",
    },
    ("doc_001", "r2"): {
        "en-fr": "Nom : Maria Garcia Lopez",
        "en-th": "ชื่อ: Maria Garcia Lopez",
        "en-ms": "Nama: Maria Garcia Lopez",
    },
    ("doc_001", "r3"): {
        "en-fr": "Date de Naissance : 14 mars 2018",
        "en-th": "วันเกิด: 14 มีนาคม 2018",
        "en-ms": "Tarikh Lahir: 14 Mac 2018",
    },
    ("doc_001", "r4"): {
        "en-fr": "Lieu de Naissance : San Salvador, El Salvador",
        "en-th": "สถานที่เกิด: ซานซัลวาดอร์, เอลซัลวาดอร์",
        "en-ms": "Tempat Lahir: San Salvador, El Salvador",
    },
    ("doc_001", "r5"): {
        "en-fr": "Sexe : Féminin",
        "en-th": "เพศ: หญิง",
        "en-ms": "Jantina: Perempuan",
    },
    ("doc_001", "r6"): {
        "en-fr": "Numéro de registre : 2018-03-1487",
        "en-th": "หมายเลขทะเบียน: 2018-03-1487",
        "en-ms": "Nombor Daftar: 2018-03-1487",
    },
    ("doc_001", "r7"): {
        "en-fr": "Délivré à San Salvador le 1er avril 2018",
        "en-th": "ออกที่ซานซัลวาดอร์ เมื่อวันที่ 1 เมษายน 2018",
        "en-ms": "Dikeluarkan di San Salvador pada 1 April 2018",
    },

    # ---------- doc_002 — Sunny Beans Coffee receipt ----------
    ("doc_002", "r1"): {
        "en-fr": "Café Sunny Beans",
        "en-th": "ซันนี่ บีนส์ คอฟฟี่",
        "en-ms": "Kedai Kopi Sunny Beans",
    },
    ("doc_002", "r2"): {
        "en-fr": "123 Main St, Portland, OR",
        "en-th": "123 ถนนเมน, พอร์ตแลนด์, รัฐออริกอน",
        "en-ms": "123 Main St, Portland, OR",
    },
    ("doc_002", "r3"): {
        "en-fr": "Café latte      $4,50",
        "en-th": "ลาเต้           $4.50",
        "en-ms": "Latte           $4.50",
    },
    ("doc_002", "r4"): {
        "en-fr": "Croissant       $3,75",
        "en-th": "ครัวซองต์       $3.75",
        "en-ms": "Croissant       $3.75",
    },
    ("doc_002", "r5"): {
        "en-fr": "Sous-total      $8,25",
        "en-th": "ยอดรวมย่อย      $8.25",
        "en-ms": "Jumlah Kecil    $8.25",
    },
    ("doc_002", "r6"): {
        "en-fr": "Taxe            $0,66",
        "en-th": "ภาษี            $0.66",
        "en-ms": "Cukai           $0.66",
    },
    ("doc_002", "r7"): {
        "en-fr": "Total           $8,91",
        "en-th": "ยอดรวม          $8.91",
        "en-ms": "Jumlah          $8.91",
    },
    ("doc_002", "r8"): {
        "en-fr": "Merci de votre visite",
        "en-th": "ขอบคุณที่มาเยือน",
        "en-ms": "Terima kasih atas kunjungan anda",
    },

    # ---------- doc_003 — Scientific paper ----------
    ("doc_003", "r1"): {
        "en-fr": "Sur le comportement asymptotique des grands modèles de langage",
        "en-th": "ว่าด้วยพฤติกรรมเชิงเส้นโค้งของแบบจำลองภาษาขนาดใหญ่",
        "en-ms": "Tentang Tingkah Laku Asimptotik Model Bahasa Besar",
    },
    ("doc_003", "r2"): {
        "en-fr": "Jane Smith, John Doe",
        "en-th": "เจน สมิธ, จอห์น โด",
        "en-ms": "Jane Smith, John Doe",
    },
    ("doc_003", "r3"): {
        "en-fr": "Résumé",
        "en-th": "บทคัดย่อ",
        "en-ms": "Abstrak",
    },
    ("doc_003", "r4"): {
        "en-fr": (
            "Nous étudions le comportement de mise à l'échelle des modèles de langage "
            "basés sur les transformateurs à mesure que le nombre de paramètres "
            "augmente. Nos résultats suggèrent une relation de loi de puissance entre "
            "la perte et le calcul."
        ),
        "en-th": (
            "เราศึกษาพฤติกรรมการขยายขนาดของแบบจำลองภาษาที่อิงทรานสฟอร์เมอร์"
            "เมื่อจำนวนพารามิเตอร์เพิ่มขึ้น ผลของเราบ่งชี้"
            "ความสัมพันธ์เชิงกฎกำลังระหว่างค่าสูญเสียกับการคำนวณ"
        ),
        "en-ms": (
            "Kami mengkaji tingkah laku penskalaan model bahasa berasaskan "
            "transformer apabila bilangan parameter bertambah. Keputusan kami "
            "mencadangkan hubungan hukum kuasa antara kehilangan dan pengiraan."
        ),
    },
    ("doc_003", "r5"): {
        "en-fr": "1. Introduction",
        "en-th": "1. บทนำ",
        "en-ms": "1. Pengenalan",
    },
    ("doc_003", "r6"): {
        "en-fr": (
            "Des travaux récents ont montré que la performance des modèles de "
            "langage suit des lois d'échelle prévisibles sur plusieurs ordres de "
            "grandeur de calcul."
        ),
        "en-th": (
            "งานวิจัยล่าสุดแสดงให้เห็นว่าประสิทธิภาพของแบบจำลองภาษา"
            "เป็นไปตามกฎการปรับขนาดที่คาดเดาได้ในระดับของการคำนวณ"
            "หลายลำดับขนาด"
        ),
        "en-ms": (
            "Kerja-kerja terkini telah menunjukkan bahawa prestasi model bahasa "
            "mengikut hukum penskalaan yang boleh diramal merentas beberapa "
            "peringkat magnitud pengiraan."
        ),
    },
    ("doc_003", "r7"): {
        "en-fr": (
            "Dans cet article, nous étendons ces résultats au régime du trillion de "
            "paramètres et examinons si l'exposant d'échelle reste stable."
        ),
        "en-th": (
            "ในบทความนี้ เราขยายผลเหล่านี้สู่ระบบล้านล้านพารามิเตอร์ "
            "และตรวจสอบว่าเลขชี้กำลังการขยายขนาดยังคงเสถียรหรือไม่"
        ),
        "en-ms": (
            "Dalam kertas ini, kami melanjutkan keputusan ini ke rejim trilion "
            "parameter dan mengkaji sama ada eksponen penskalaan kekal stabil."
        ),
    },
    ("doc_003", "r8"): {
        "en-fr": "Figure 1. Perte en fonction du calcul d'entraînement (log-log).",
        "en-th": "รูปที่ 1. ค่าสูญเสียในฐานะฟังก์ชันของการคำนวณการฝึก (log-log).",
        "en-ms": "Rajah 1. Kehilangan sebagai fungsi pengiraan latihan (log-log).",
    },

    # ---------- doc_004 — Business letter ----------
    ("doc_004", "r1"): {
        "en-fr": "Acme Industries Inc.",
        "en-th": "Acme Industries Inc.",
        "en-ms": "Acme Industries Sdn. Bhd.",
    },
    ("doc_004", "r2"): {
        "en-fr": "15 janvier 2026",
        "en-th": "15 มกราคม 2026",
        "en-ms": "15 Januari 2026",
    },
    ("doc_004", "r3"): {
        "en-fr": "M. Robert Chen\n42 Oak Avenue\nBoston, MA 02101",
        "en-th": "คุณโรเบิร์ต เฉิน\n42 ถนนโอ๊ค\nบอสตัน รัฐแมสซาชูเซตส์ 02101",
        "en-ms": "Tuan Robert Chen\n42 Oak Avenue\nBoston, MA 02101",
    },
    ("doc_004", "r4"): {
        "en-fr": "Monsieur Chen,",
        "en-th": "เรียน คุณเฉิน,",
        "en-ms": "Yang Berhormat Tuan Chen,",
    },
    ("doc_004", "r5"): {
        "en-fr": (
            "Nous vous remercions de l'intérêt que vous portez à nos services aux "
            "entreprises. Nous avons le plaisir de confirmer notre proposition pour "
            "l'exercice à venir et nous nous réjouissons de poursuivre notre "
            "partenariat."
        ),
        "en-th": (
            "ขอขอบคุณที่ท่านสนใจในบริการระดับองค์กรของเรา "
            "เรายินดีที่จะยืนยันข้อเสนอสำหรับปีงบประมาณที่จะถึงนี้ "
            "และหวังเป็นอย่างยิ่งว่าจะได้ร่วมงานกันต่อไป"
        ),
        "en-ms": (
            "Terima kasih atas minat anda terhadap perkhidmatan korporat kami. "
            "Kami dengan sukacitanya mengesahkan cadangan kami untuk tahun "
            "kewangan akan datang dan menantikan kerjasama yang berterusan."
        ),
    },
    ("doc_004", "r6"): {
        "en-fr": "Cordialement,",
        "en-th": "ขอแสดงความนับถือ,",
        "en-ms": "Yang Benar,",
    },
    ("doc_004", "r7"): {
        "en-fr": "Alice Thompson, Directrice Générale",
        "en-th": "อลิซ ทอมป์สัน, ประธานเจ้าหน้าที่บริหาร",
        "en-ms": "Alice Thompson, Ketua Pegawai Eksekutif",
    },

    # ---------- doc_005 — Handwritten meeting notes ----------
    ("doc_005", "r1"): {
        "en-fr": "Notes de réunion — Planification T1",
        "en-th": "บันทึกการประชุม — การวางแผนไตรมาส 1",
        "en-ms": "Nota Mesyuarat — Perancangan S1",
    },
    ("doc_005", "r2"): {
        "en-fr": "Actions à mener :",
        "en-th": "รายการที่ต้องดำเนินการ:",
        "en-ms": "Tindakan:",
    },
    ("doc_005", "r3"): {
        "en-fr": "1. Embaucher deux ingénieurs",
        "en-th": "1. จ้างวิศวกรสองคน",
        "en-ms": "1. Mengambil dua jurutera",
    },
    ("doc_005", "r4"): {
        "en-fr": "2. Livrer le MVP d'ici avril",
        "en-th": "2. ส่งมอบ MVP ภายในเดือนเมษายน",
        "en-ms": "2. Hantar MVP menjelang April",
    },
    ("doc_005", "r5"): {
        "en-fr": "3. Entretiens clients",
        "en-th": "3. สัมภาษณ์ลูกค้า",
        "en-ms": "3. Temu duga pelanggan",
    },
}


def main(annotations_dir: Path = Path("data/annotations")) -> int:
    annotations = sorted(annotations_dir.glob("doc_*.json"))
    updated = 0
    skipped = 0
    for ann_path in annotations:
        with ann_path.open("r", encoding="utf-8") as f:
            ann: dict[str, Any] = json.load(f)

        doc_id = ann["doc_id"]
        per_region = 0
        for region in ann["regions"]:
            key = (doc_id, region["region_id"])
            additions = REFS.get(key)
            if not additions:
                print(f"  WARN: no translations defined for {doc_id}/{region['region_id']}")
                skipped += 1
                continue
            refs = region.setdefault("references", {})
            for lang_pair, text in additions.items():
                if lang_pair in refs:
                    continue  # idempotent: keep existing
                refs[lang_pair] = text
            per_region += 1

        with ann_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(ann, f, ensure_ascii=False, indent=2)
            f.write("\n")

        print(f"  updated {doc_id} ({per_region} regions)")
        updated += 1

    print(f"\nDone — updated {updated} files, skipped {skipped} regions without translations.")
    return 0 if skipped == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

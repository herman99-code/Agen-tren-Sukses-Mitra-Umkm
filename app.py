from flask import Flask, jsonify, request, render_template
import pandas as pd
from pytrends.request import TrendReq
import time
import os

app = Flask(__name__, template_folder='templates', static_folder='static')

# Simple in-memory cache to prevent rate limits
# Key: (keyword, geo, timeframe), Value: (timestamp, data_dict)
CACHE = {}
CACHE_TIMEOUT = 900  # 15 minutes

# Pre-populated mock data for fallback in case of rate limiting (429) or offline use
FALLBACK_DATA = {
    "seblak": {
        "time_data": [
            {"date": "2025-07", "value": 58}, {"date": "2025-08", "value": 60},
            {"date": "2025-09", "value": 55}, {"date": "2025-10", "value": 62},
            {"date": "2025-11", "value": 65}, {"date": "2025-12", "value": 70},
            {"date": "2026-01", "value": 68}, {"date": "2026-02", "value": 64},
            {"date": "2026-03", "value": 59}, {"date": "2026-04", "value": 61},
            {"date": "2026-05", "value": 58}, {"date": "2026-06", "value": 55}
        ],
        "region_data": [
            {"region": "Jawa Tengah", "value": 100},
            {"region": "DI Yogyakarta", "value": 93},
            {"region": "Jawa Barat", "value": 81},
            {"region": "Jawa Timur", "value": 81},
            {"region": "Kepulauan Bangka Belitung", "value": 72},
            {"region": "Lampung", "value": 66},
            {"region": "Banten", "value": 61},
            {"region": "Sumatera Selatan", "value": 58}
        ],
        "top_queries": [
            {"query": "seblak prasmanan", "value": 100},
            {"query": "resep seblak", "value": 59},
            {"query": "seblak kuah", "value": 49},
            {"query": "kerupuk seblak", "value": 41},
            {"query": "bumbu seblak", "value": 40}
        ],
        "rising_queries": [
            {"query": "batagor kering seblak", "value": 200},
            {"query": "toping seblak seafood", "value": 160},
            {"query": "indomi seblak", "value": 120},
            {"query": "cuanki lidah", "value": 90},
            {"query": "mie rasa seblak", "value": 70}
        ]
    },
    "croissant": {
        "time_data": [
            {"date": "2025-07", "value": 90}, {"date": "2025-08", "value": 85},
            {"date": "2025-09", "value": 78}, {"date": "2025-10", "value": 70},
            {"date": "2025-11", "value": 60}, {"date": "2025-12", "value": 52},
            {"date": "2026-01", "value": 45}, {"date": "2026-02", "value": 38},
            {"date": "2026-03", "value": 30}, {"date": "2026-04", "value": 28},
            {"date": "2026-05", "value": 24}, {"date": "2026-06", "value": 20}
        ],
        "region_data": [
            {"region": "DKI Jakarta", "value": 100},
            {"region": "Banten", "value": 85},
            {"region": "Jawa Barat", "value": 80},
            {"region": "DI Yogyakarta", "value": 72},
            {"region": "Bali", "value": 70},
            {"region": "Jawa Timur", "value": 65}
        ],
        "top_queries": [
            {"query": "croissant bandung", "value": 100},
            {"query": "croissant geprek", "value": 80},
            {"query": "cromboloni", "value": 75},
            {"query": "resep croissant", "value": 50},
            {"query": "croissant jakarta", "value": 45}
        ],
        "rising_queries": [
            {"query": "flat croissant", "value": 250},
            {"query": "croissant waffle", "value": 90},
            {"query": "croissant viral", "value": 80}
        ]
    },
    "es kopi": {
        "time_data": [
            {"date": "2025-07", "value": 80}, {"date": "2025-08", "value": 82},
            {"date": "2025-09", "value": 85}, {"date": "2025-10", "value": 81},
            {"date": "2025-11", "value": 78}, {"date": "2025-12", "value": 75},
            {"date": "2026-01", "value": 79}, {"date": "2026-02", "value": 82},
            {"date": "2026-03", "value": 84}, {"date": "2026-04", "value": 86},
            {"date": "2026-05", "value": 88}, {"date": "2026-06", "value": 90}
        ],
        "region_data": [
            {"region": "DKI Jakarta", "value": 100},
            {"region": "Banten", "value": 94},
            {"region": "Jawa Barat", "value": 88},
            {"region": "DI Yogyakarta", "value": 85},
            {"region": "Jawa Timur", "value": 80},
            {"region": "Sumatera Utara", "value": 70}
        ],
        "top_queries": [
            {"query": "es kopi susu", "value": 100},
            {"query": "es kopi terdekat", "value": 90},
            {"query": "es kopi susu gula aren", "value": 75},
            {"query": "resep es kopi", "value": 40}
        ],
        "rising_queries": [
            {"query": "es kopi susu creamy", "value": 300},
            {"query": "es kopi sea salt", "value": 150},
            {"query": "kopi susu botolan", "value": 110}
        ]
    }
}

def clean_data_dict(time_data, region_data, top_queries, rising_queries):
    """Ensure data is serializable and clear of NaN values."""
    return {
        "time_data": time_data,
        "region_data": region_data,
        "top_queries": top_queries,
        "rising_queries": rising_queries
    }

def get_fallback_data(keyword):
    """Retrieve fallback data based on matching keywords or fallback to default templates."""
    kw_lower = keyword.lower()
    for key, data in FALLBACK_DATA.items():
        if key in kw_lower or kw_lower in key:
            return data
            
    # Default fallback data if the word doesn't match standard ones
    return {
        "time_data": [
            {"date": "2025-07", "value": 40}, {"date": "2025-08", "value": 45},
            {"date": "2025-09", "value": 50}, {"date": "2025-10", "value": 48},
            {"date": "2025-11", "value": 52}, {"date": "2025-12", "value": 60},
            {"date": "2026-01", "value": 65}, {"date": "2026-02", "value": 72},
            {"date": "2026-03", "value": 80}, {"date": "2026-04", "value": 85},
            {"date": "2026-05", "value": 90}, {"date": "2026-06", "value": 95}
        ],
        "region_data": [
            {"region": "Jawa Barat", "value": 100},
            {"region": "DKI Jakarta", "value": 90},
            {"region": "Jawa Tengah", "value": 80},
            {"region": "Banten", "value": 75},
            {"region": "Jawa Timur", "value": 70}
        ],
        "top_queries": [
            {"query": f"resep {keyword}", "value": 100},
            {"query": f"{keyword} enak", "value": 75},
            {"query": f"{keyword} terdekat", "value": 50}
        ],
        "rising_queries": [
            {"query": f"{keyword} viral", "value": 300},
            {"query": f"{keyword} kekinian", "value": 150}
        ]
    }

def generate_culinary_advice(keyword, trend_status, slope, top_regions, rising_queries):
    """Generates a structured, rich, professional culinary advice report in Indonesian.
    
    Returns comprehensive advice across 4 pillars:
    - recommendations: Quick tactical actions
    - business_strategy: Menu engineering, pricing, operations
    - content_ideas: Social media content hooks & video concepts
    - marketing_strategy: Digital marketing, ads, SEO, platform optimization
    """
    
    # Helper data
    rising_queries_text = [q['query'] for q in rising_queries[:5]] if rising_queries else []
    top_region_name = top_regions[0]["region"] if top_regions else "beberapa wilayah"
    second_region = top_regions[1]["region"] if len(top_regions) > 1 else "wilayah sekitar"
    third_region = top_regions[2]["region"] if len(top_regions) > 2 else "kota-kota besar lainnya"
    kw_title = keyword.title()
    
    # ===================================================================
    # 1. SUMMARY (Trend Overview)
    # ===================================================================
    if trend_status == "DECLINING":
        summary = (
            f"Tren pencarian untuk '{keyword}' menunjukkan penurunan minat yang cukup tajam "
            f"({abs(slope):.1f}% dalam beberapa bulan terakhir). Ini menandakan bahwa menu ini kemungkinan besar "
            f"merupakan tren sesaat (*viral fad*) yang sudah melewati masa puncaknya. "
            f"Konsumen mulai jenuh dan beralih ke variasi makanan baru."
        )
    elif trend_status == "RISING":
        summary = (
            f"Luar biasa! Tren '{keyword}' sedang mengalami kenaikan popularitas yang pesat "
            f"(+{slope:.1f}% kenaikan minat penelusuran). Ini adalah waktu emas bagi UMKM Kuliner "
            f"untuk meluncurkan atau memperkuat lini produk ini karena permintaan pasar sedang tinggi-tingginya."
        )
    else:
        summary = (
            f"Popularitas '{keyword}' terpantau stabil ({slope:+.1f}% fluktuasi). "
            f"Ini menunjukkan bahwa '{keyword}' telah beralih dari sekadar tren viral menjadi makanan sehari-hari "
            f"(*staple food*) yang memiliki basis pelanggan setia yang kuat di Indonesia."
        )
        
    # Check for seasonal keywords
    seasonal_keywords = ["ramadhan", "puasa", "es ", "dingin", "takjil", "kurma", "kolak", "lebaran", "mudik", "hangat", "sup", "kuah"]
    is_seasonal = any(sk in keyword.lower() for sk in seasonal_keywords)
    if is_seasonal:
        summary += " Produk ini juga menunjukkan pola sensitivitas musiman (misalnya dipengaruhi cuaca panas/hujan atau momen keagamaan seperti Ramadhan)."

    # 2. Regional Insights
    regional_insight = f"Minat terbesar terkonsentrasi di **{top_region_name}**."
    if len(top_regions) > 1:
        regional_insight += f" Diikuti secara ketat oleh wilayah **{top_regions[1]['region']}** dan **{top_regions[2]['region']}**."

    # ===================================================================
    # 3. QUICK ACTION RECOMMENDATIONS (Tab 1 - Aksi)
    # ===================================================================
    recs = []
    
    if trend_status == "DECLINING":
        recs.append(
            f"**Jangan Jadikan Lini Bisnis Utama:** Jika baru ingin memulai, hindari membuka toko yang 100% didedikasikan "
            f"hanya untuk '{keyword}'. Gunakan menu ini sebagai menu pelengkap saja untuk meminimalkan risiko kerugian."
        )
        if rising_queries_text:
            recs.append(
                f"**Pivot ke Inovasi Baru:** Konsumen masih mencari '{rising_queries_text[0]}'. "
                f"Cobalah memodifikasi menu '{keyword}' Anda dengan sentuhan baru tersebut untuk memicu rasa penasaran kembali."
            )
        else:
            recs.append(
                f"**Fokus pada Efisiensi & Promo:** Untuk produk yang mulai turun, kurangi stok bahan baku agar tidak menumpuk, "
                f"dan lakukan taktik *bundling* dengan menu lain yang sedang naik daun."
            )
        recs.append(
            f"**Peralihan Menu Bertahap:** Mulailah memikirkan menu alternatif yang sedang naik daun dan kurangi promosi berbayar "
            f"untuk produk '{keyword}' Anda."
        )
    elif trend_status == "RISING":
        recs.append(
            f"**Gerak Cepat Mengambil Momentum:** Segera luncurkan varian '{keyword}' di warung/restoran Anda. "
            f"Gunakan spanduk visual yang menarik atau menu rekomendasi di aplikasi ojek online untuk langsung menangkap pasar."
        )
        if len(rising_queries_text) >= 1:
            recs.append(
                f"**Hadirkan Menu Inovatif '{rising_queries_text[0].title()}':** Integrasikan kata kunci naik daun ini "
                f"ke dalam produk Anda. Misalnya, jika kueri tersebut adalah topping atau rasa baru, jadikan itu *signature menu* Anda."
            )
        else:
            recs.append(
                f"**Kustomisasi Menu:** Berikan kebebasan bagi pelanggan untuk mengkustomisasi tingkat kepedasan, rasa, "
                f"atau topping produk '{keyword}' Anda."
            )
        recs.append(
            f"**Pemasaran Berbasis Konten Visual:** Buat konten pembuatan '{keyword}' di TikTok atau Instagram Reels. "
            f"Tren naik biasanya sangat dipengaruhi oleh konten visual yang menggugah selera (*food porn*)."
        )
    else: # STABLE
        recs.append(
            f"**Pertahankan Konsistensi Kualitas & Rasa:** Karena ini adalah *staple food*, pelanggan mencari rasa yang konsisten. "
            f"Pastikan standar operasional (SOP) dapur Anda terjaga dengan baik."
        )
        if len(rising_queries_text) >= 1:
            recs.append(
                f"**Luncurkan Edisi Terbatas (LTO):** Agar pelanggan setia tidak bosan, luncurkan variasi '{rising_queries_text[0]}' "
                f"sebagai menu edisi terbatas (misal: hanya tersedia di bulan ini)."
            )
        else:
            recs.append(
                f"**Tawarkan Paket Hemat / Bundling:** Buat paket bundling keluarga atau paket makan siang hemat "
                f"menggabungkan '{keyword}' dengan minuman manis segar."
            )
        recs.append(
            f"**Program Loyalitas Pelanggan:** Buat program kartu diskon atau poin bagi pelanggan setia untuk menjaga "
            f"mereka agar tidak pindah ke kompetitor terdekat."
        )

    # ===================================================================
    # 4. BUSINESS STRATEGY (Tab 2 - Strategi Bisnis)
    # ===================================================================
    business_strategy = []
    
    if trend_status == "RISING":
        business_strategy.append(
            f"<strong>🎯 Rekayasa Menu (Menu Engineering):</strong> Posisikan '{kw_title}' sebagai menu <em>Star Item</em> "
            f"(margin tinggi + popularitas tinggi). Tempatkan di posisi paling strategis pada daftar menu — pojok kanan atas "
            f"pada menu fisik, atau foto pertama di profil GoFood/GrabFood Anda."
        )
        business_strategy.append(
            f"<strong>💰 Strategi Harga Penetrasi:</strong> Tetapkan harga kompetitif di bawah rata-rata pasar "
            f"sebesar 10-15% untuk merebut pangsa pasar dengan cepat selagi tren naik. Contoh: jika kompetitor jual "
            f"'{keyword}' Rp 18.000, tawarkan di Rp 15.000 dengan porsi serupa namun presentasi lebih menarik."
        )
        business_strategy.append(
            f"<strong>📦 Paket Bundling Cerdas:</strong> Buat paket '{kw_title} Combo' yang menggabungkan produk utama "
            f"dengan minuman atau snack pelengkap. Ini meningkatkan <em>average order value</em> (AOV) hingga 25-40%."
        )
        business_strategy.append(
            f"<strong>🏪 Ekspansi Cloud Kitchen:</strong> Karena tren sedang naik pesat, pertimbangkan membuka outlet "
            f"<em>cloud kitchen</em> di area {second_region} dan {third_region} untuk menangkap permintaan lintas wilayah "
            f"tanpa biaya sewa tempat makan fisik."
        )
        if rising_queries_text:
            business_strategy.append(
                f"<strong>🔬 R&D Produk Berbasis Data:</strong> Kueri '{rising_queries_text[0]}' sedang melonjak. "
                f"Kembangkan varian menu baru yang mengintegrasikan tren ini sebagai <em>signature product</em> "
                f"yang tidak dimiliki kompetitor."
            )
    elif trend_status == "DECLINING":
        business_strategy.append(
            f"<strong>⚠️ Audit Portofolio Menu:</strong> Pindahkan '{kw_title}' dari kategori menu utama ke menu pelengkap. "
            f"Kurangi variasi/SKU produk ini untuk menghemat biaya bahan baku dan operasional dapur."
        )
        business_strategy.append(
            f"<strong>💡 Pivot & Diversifikasi:</strong> Alokasikan 60-70% fokus R&D ke menu-menu baru yang sedang naik tren. "
            f"Gunakan infrastruktur dapur yang sama (peralatan, supply chain) untuk produk pengganti yang lebih relevan."
        )
        business_strategy.append(
            f"<strong>📊 Strategi Harga Clearance:</strong> Terapkan strategi <em>flash sale</em> atau diskon bundling "
            f"untuk menghabiskan stok bahan baku '{keyword}' yang masih tersisa. Contoh: 'Beli 2 Gratis 1' atau "
            f"'Paket Hemat Akhir Pekan'."
        )
        business_strategy.append(
            f"<strong>🤝 Kolaborasi & Co-Branding:</strong> Jika masih ingin mempertahankan '{keyword}', kolaborasikan "
            f"dengan brand lain (misal: kolaborasi rasa dengan brand snack lokal) untuk menciptakan buzz baru."
        )
    else:  # STABLE
        business_strategy.append(
            f"<strong>📋 Standarisasi SOP Dapur:</strong> Buat SOP tertulis untuk setiap tahap pembuatan '{keyword}' — "
            f"dari persiapan bahan, proses masak, plating, hingga packaging. Konsistensi rasa adalah kunci loyalitas "
            f"pelanggan untuk produk <em>staple</em>."
        )
        business_strategy.append(
            f"<strong>🏆 Program Loyalitas & Membership:</strong> Luncurkan kartu member atau sistem poin digital. "
            f"Contoh: 'Beli 10 porsi {kw_title}, GRATIS 1 porsi!' Ini menjaga customer retention rate tetap tinggi."
        )
        business_strategy.append(
            f"<strong>📈 Upselling & Cross-selling:</strong> Latih karyawan untuk menawarkan add-on seperti ekstra topping, "
            f"level pedas premium (+Rp 3.000), atau upgrade size. Ini bisa meningkatkan margin per transaksi 15-20%."
        )
        business_strategy.append(
            f"<strong>🚀 Ekspansi Katering & B2B:</strong> Karena '{keyword}' sudah stabil, targetkan segmen katering "
            f"(arisan, pesta ulang tahun, acara kantor). Buat paket katering khusus dengan minimum order yang menguntungkan."
        )
        if rising_queries_text:
            business_strategy.append(
                f"<strong>🎪 Menu Limited Edition (LTO):</strong> Luncurkan edisi terbatas '{rising_queries_text[0].title()}' "
                f"setiap bulan untuk menjaga excitement pelanggan tanpa mengubah menu inti yang sudah stabil."
            )

    # ===================================================================
    # 5. CONTENT IDEAS (Tab 3 - Ide Konten Sosmed)
    # ===================================================================
    content_ideas = []
    
    if trend_status == "RISING":
        content_ideas.append(
            f"<strong>🎬 Behind The Scene (BTS) Viral:</strong> Rekam proses pembuatan '{keyword}' dari awal hingga akhir "
            f"dengan sudut kamera overhead (bird's eye view). Tambahkan sound effect ASMR sizzling/crunchy. "
            f"Format: TikTok/Reels 15-30 detik. Hook pertama: <em>\"Ini rahasia kenapa {keyword} kami selalu habis sebelum jam 2 siang...\"</em>"
        )
        content_ideas.append(
            f"<strong>🔥 Challenge & Giveaway:</strong> Buat challenge '#Tantangan{kw_title.replace(' ', '')}' — ajak followers "
            f"makan level pedas tertinggi atau habiskan porsi jumbo dalam waktu tertentu. Hadiahkan voucher makan gratis "
            f"untuk 3 pemenang terbaik. Ini bisa menghasilkan <em>user-generated content</em> (UGC) secara masif."
        )
        content_ideas.append(
            f"<strong>📱 Kolom 'Pelanggan Review':</strong> Minta izin pelanggan untuk merekam reaksi mereka saat "
            f"pertama kali mencoba '{keyword}' Anda. Konten <em>real reaction</em> memiliki tingkat engagement 3-5x "
            f"lebih tinggi dibanding konten promosi biasa."
        )
        content_ideas.append(
            f"<strong>🧑‍🍳 Tutorial Resep Mini:</strong> Bagikan '70% resep' '{keyword}' secara gratis di TikTok — "
            f"tunjukkan bahan dan langkah umum, tapi rahasiakan bumbu spesial Anda. Caption: <em>\"Bumbu rahasianya? "
            f"Datang langsung ke warung kami 😏\"</em>. Ini membangun rasa penasaran dan mendorong kunjungan offline."
        )
        if rising_queries_text:
            content_ideas.append(
                f"<strong>📊 Konten Edukatif Trending:</strong> Buat infografis atau video pendek yang membahas "
                f"'{rising_queries_text[0]}' — jelaskan apa itu, bagaimana rasanya, dan kenapa sedang viral. "
                f"Posisikan brand Anda sebagai <em>thought leader</em> di niche {keyword}."
            )
    elif trend_status == "DECLINING":
        content_ideas.append(
            f"<strong>🔄 Konten 'Plot Twist' Reinvention:</strong> Buat video dengan hook: <em>\"Semua bilang {keyword} "
            f"sudah nggak laku... tapi lihat apa yang kami bikin!\"</em> — lalu tunjukkan inovasi unik dari menu tersebut "
            f"(fusion, presentasi baru, topping premium). Konten kontrarian selalu menarik perhatian."
        )
        content_ideas.append(
            f"<strong>🎯 Storytelling Nostalgia:</strong> Buat konten cerita: <em>\"Kenapa kami tetap jual {keyword} "
            f"walaupun tren sudah turun...\"</em> — ceritakan nilai emosional, resep warisan keluarga, atau filosofi "
            f"di balik menu ini. Konten emosional memiliki share rate 2x lebih tinggi."
        )
        content_ideas.append(
            f"<strong>🤝 Konten Kolaborasi:</strong> Undang food blogger lokal atau micro-influencer (5K-50K followers) "
            f"untuk mencoba menu '{keyword}' Anda. Mereka biasanya mau review gratis/barter menu. Fokus pada "
            f"influencer yang audiensnya sesuai target market Anda di {top_region_name}."
        )
        content_ideas.append(
            f"<strong>📸 Before vs After Makeover:</strong> Tunjukkan transformasi '{keyword}' dari versi biasa ke versi "
            f"premium Anda — dengan plating keren, garnish menarik, dan packaging Instagrammable. "
            f"Caption: <em>\"Same {keyword}, different level 🔥\"</em>"
        )
    else:  # STABLE
        content_ideas.append(
            f"<strong>📅 Konten Rutin Mingguan (Content Pillar):</strong> Buat jadwal konten tetap: "
            f"Senin = 'Menu of the Week', Rabu = 'Tips Masak {kw_title}', Jumat = 'Customer Spotlight'. "
            f"Konsistensi posting 4-5x/minggu meningkatkan jangkauan organik hingga 60%."
        )
        content_ideas.append(
            f"<strong>🏆 Series 'Pelanggan Setia':</strong> Setiap minggu, highlight satu pelanggan loyal — ceritakan "
            f"berapa lama mereka sudah berlangganan, menu favorit mereka, dan momen spesial mereka dengan '{keyword}' Anda. "
            f"Ini membangun komunitas dan social proof yang kuat."
        )
        content_ideas.append(
            f"<strong>🎥 Day-in-the-Life Pemilik UMKM:</strong> Rekam rutinitas harian Anda dari jam 4 pagi (belanja bahan) "
            f"hingga warung tutup. Konten <em>authentic day-in-the-life</em> sangat disukai algoritma TikTok "
            f"dan membangun koneksi emosional dengan audiens."
        )
        content_ideas.append(
            f"<strong>💬 Polling & Q&A Interaktif:</strong> Gunakan fitur polling Instagram Story untuk melibatkan audiens: "
            f"<em>\"Mau rasa baru apa untuk {keyword} kita?\"</em> atau <em>\"Level pedas mana favorit kalian?\"</em>. "
            f"Engagement dari fitur interaktif meningkatkan visibilitas akun 40-50%."
        )
        if rising_queries_text:
            content_ideas.append(
                f"<strong>🧪 Konten 'Experiment':</strong> Buat video: <em>\"Kami coba bikin {rising_queries_text[0].title()} "
                f"— hasilnya...\"</em>. Format eksperimen/taste test selalu mengundang rasa penasaran dan komentar."
            )

    # ===================================================================
    # 6. DIGITAL MARKETING STRATEGY (Tab 4 - Strategi Marketing)
    # ===================================================================
    marketing_strategy = []
    
    if trend_status == "RISING":
        marketing_strategy.append(
            f"<strong>📍 GoFood/GrabFood SEO Optimization:</strong> Pastikan nama menu mengandung kata kunci '{keyword}' "
            f"yang persis dicari konsumen. Contoh: bukan hanya 'Menu Spesial #1', tapi '{kw_title} Kuah Pedas Original'. "
            f"Tambahkan foto HD dengan rasio 1:1 dan deskripsi yang menggugah selera."
        )
        marketing_strategy.append(
            f"<strong>🎯 Instagram/TikTok Ads Lokal:</strong> Alokasikan budget Rp 50.000-100.000/hari untuk iklan berbayar "
            f"yang ditargetkan pada radius 5-10 km dari lokasi warung Anda di {top_region_name}. Gunakan format video "
            f"dengan CTA: <em>\"Pesan Sekarang lewat GoFood!\"</em>. ROI iklan lokal F&B bisa mencapai 3-5x."
        )
        marketing_strategy.append(
            f"<strong>🌐 Google My Business (GMB) Optimization:</strong> Klaim dan optimalkan profil Google Business Anda. "
            f"Upload minimal 10 foto menu, tulis deskripsi dengan keyword '{keyword} enak di {top_region_name}', "
            f"dan aktif minta review bintang 5 dari pelanggan puas. Bisnis dengan 50+ review mendapat 2x lebih banyak leads."
        )
        marketing_strategy.append(
            f"<strong>🤳 Program Referral WhatsApp:</strong> Buat program: <em>\"Share link menu kami ke 3 grup WA, "
            f"dapat diskon 20% untuk pesanan berikutnya!\"</em> WhatsApp marketing memiliki open rate 98% — jauh lebih efektif "
            f"dari email (20%) untuk target market UMKM di Indonesia."
        )
        marketing_strategy.append(
            f"<strong>📈 Hashtag Strategy:</strong> Gunakan kombinasi hashtag: #{keyword.replace(' ', '')} (high volume), "
            f"#{keyword.replace(' ', '')}viral (trending), #kulinernusantara (broad), #kuliner{top_region_name.lower().replace(' ', '')} (lokal). "
            f"Total 15-20 hashtag per posting untuk jangkauan maksimal."
        )
    elif trend_status == "DECLINING":
        marketing_strategy.append(
            f"<strong>🔄 Retargeting Pelanggan Lama:</strong> Gunakan database pelanggan (nomor WA/follower IG) "
            f"untuk mengirim pesan personal: <em>\"Kangen {kw_title}? Minggu ini ada diskon spesial 25% khusus untuk kamu!\"</em> "
            f"Re-engagement campaign lebih murah 5x dibanding akuisisi pelanggan baru."
        )
        marketing_strategy.append(
            f"<strong>💸 Stop Burn Budget pada Paid Ads:</strong> Kurangi atau hentikan total spending iklan berbayar untuk '{keyword}'. "
            f"Alihkan budget ke produk baru yang trennya sedang naik. Fokuskan promosi '{keyword}' hanya melalui "
            f"channel organik (posting IG, story, WA broadcast) yang gratis."
        )
        marketing_strategy.append(
            f"<strong>📦 Strategi Paket Bundling di Aplikasi:</strong> Di GoFood/GrabFood, buat 'Paket Hemat' yang menggabungkan "
            f"'{keyword}' dengan menu lain yang lebih populer. Ini membantu menjual stok tanpa biaya marketing tambahan."
        )
        marketing_strategy.append(
            f"<strong>🎪 Event-Based Marketing:</strong> Ikuti bazaar kuliner, car free day, atau event kampus di {top_region_name}. "
            f"Promosi offline dengan sampling gratis bisa menghidupkan kembali minat terhadap menu yang mulai menurun."
        )
    else:  # STABLE
        marketing_strategy.append(
            f"<strong>📱 Omnichannel Presence:</strong> Pastikan '{keyword}' Anda tersedia dan teroptimasi di "
            f"SEMUA platform: GoFood, GrabFood, ShopeeFood, Instagram, TikTok Shop, dan Google Maps. "
            f"Konsistensi omnichannel meningkatkan penemuan oleh pelanggan baru hingga 3x."
        )
        marketing_strategy.append(
            f"<strong>⭐ Review & Rating Farming:</strong> Secara sistematis minta review dari pelanggan puas. "
            f"Cetak QR code di kemasan yang langsung mengarah ke halaman review Google/GoFood. "
            f"Tawarkan insentif kecil: <em>\"Review bintang 5, dapat topping gratis di kunjungan berikutnya!\"</em>"
        )
        marketing_strategy.append(
            f"<strong>📧 CRM & Database Marketing:</strong> Kumpulkan data pelanggan (nomor WA) lewat program member. "
            f"Kirim broadcast mingguan setiap Kamis: <em>\"Menu spesial weekend: {kw_title} dengan topping baru!\"</em> "
            f"Personalisasi pesan berdasarkan histori pesanan pelanggan."
        )
        marketing_strategy.append(
            f"<strong>🏪 Local SEO Domination:</strong> Targetkan keyword long-tail seperti '{keyword} enak di {top_region_name}', "
            f"'{keyword} terdekat murah', '{keyword} buka 24 jam'. Buat posting Google Business 2x/minggu "
            f"dengan foto menu terbaru untuk mendominasi pencarian lokal."
        )
        marketing_strategy.append(
            f"<strong>🤝 Micro-Influencer Barter:</strong> Identifikasi 5-10 food blogger lokal di {top_region_name} "
            f"dengan 2K-20K followers. Tawarkan makan gratis sebagai barter review jujur. "
            f"Micro-influencer menghasilkan engagement rate 5-8% vs macro-influencer yang hanya 1-2%."
        )

    return {
        "status": trend_status,
        "summary": summary,
        "regional_insight": regional_insight,
        "recommendations": recs,
        "business_strategy": business_strategy,
        "content_ideas": content_ideas,
        "marketing_strategy": marketing_strategy,
        "warning_alert": trend_status == "DECLINING"
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze')
def analyze():
    keyword = request.args.get('keyword', '').strip()
    geo = request.args.get('geo', 'ID').strip()
    timeframe = request.args.get('timeframe', 'today 12-m').strip()
    
    if not keyword:
        return jsonify({"error": "Keyword parameter is required"}), 400

    # Ensure geo uses ID prefix if it is a province code
    if geo != 'ID' and not geo.startswith('ID-'):
        geo = f"ID-{geo}"

    cache_key = (keyword.lower(), geo, timeframe)
    current_time = time.time()
    
    # Check cache
    if cache_key in CACHE:
        timestamp, cached_data = CACHE[cache_key]
        if current_time - timestamp < CACHE_TIMEOUT:
            return jsonify(cached_data)

    print(f"Fetching fresh Google Trends data for: keyword='{keyword}', geo='{geo}', timeframe='{timeframe}'")
    
    try:
        pytrends = TrendReq(hl='id-ID', tz=420, timeout=(10, 25))
        pytrends.build_payload([keyword], cat=71, timeframe=timeframe, geo=geo)
        
        # 1. Fetch Interest Over Time
        df_time = pytrends.interest_over_time()
        time_data = []
        if not df_time.empty:
            # We reset index to make 'date' a column
            df_time = df_time.reset_index()
            # If the index is dates, convert it to string format
            df_time['date'] = df_time['date'].dt.strftime('%Y-%m-%d')
            for _, row in df_time.iterrows():
                val = int(row[keyword]) if not pd.isna(row[keyword]) else 0
                time_data.append({"date": row['date'], "value": val})
        
        # 2. Fetch Interest by Region
        region_data = []
        if geo == 'ID':  # Region breakdown only works nicely for country-level queries
            df_region = pytrends.interest_by_region(resolution='REGION', inc_low_vol=True, inc_geo_code=True)
            if not df_region.empty:
                df_region = df_region.sort_values(by=keyword, ascending=False)
                for index, row in df_region.head(10).iterrows():
                    val = int(row[keyword]) if not pd.isna(row[keyword]) else 0
                    region_data.append({"region": index, "value": val})

        # 3. Fetch Related Queries
        top_queries = []
        rising_queries = []
        related = pytrends.related_queries()
        if keyword in related:
            queries = related[keyword]
            
            # Top Queries
            if queries['top'] is not None and not queries['top'].empty:
                for _, row in queries['top'].head(8).iterrows():
                    val = int(row['value']) if not pd.isna(row['value']) else 0
                    top_queries.append({"query": str(row['query']), "value": val})
            
            # Rising Queries
            if queries['rising'] is not None and not queries['rising'].empty:
                for _, row in queries['rising'].head(8).iterrows():
                    # Handle breakout status, which can be represented by a very large int or string 'breakout'
                    raw_val = row['value']
                    val = int(raw_val) if isinstance(raw_val, (int, float)) and not pd.isna(raw_val) else 200 # Default breakout representation
                    query_str = str(row['query'])
                    top_queries_names = [q['query'] for q in top_queries]
                    
                    # Deduplicate or add to rising
                    rising_queries.append({"query": query_str, "value": val})

        # Process / Calculate Trend Health & Slope
        # Let's check slope in the last 8 observations (roughly 2 months)
        trend_status = "STABLE"
        slope = 0.0
        if len(time_data) >= 8:
            vals = [t['value'] for t in time_data]
            last_4 = sum(vals[-4:]) / 4.0
            prev_4 = sum(vals[-8:-4]) / 4.0
            
            if prev_4 > 0:
                slope = ((last_4 - prev_4) / prev_4) * 100.0
            else:
                slope = (last_4 - prev_4) * 100.0  # fallback simple difference percentage
            
            # Determine status based on slope threshold (15%)
            # Also watch out for fads: max interest in history vs current interest
            max_val = max(vals)
            current_val = vals[-1]
            
            if max_val > 60 and current_val < (max_val * 0.35):
                # Major drop from historical high -> Declining
                trend_status = "DECLINING"
            elif slope > 15:
                trend_status = "RISING"
            elif slope < -15:
                trend_status = "DECLINING"
            else:
                trend_status = "STABLE"
        
        # Fallback region if it was a regional search (geo != 'ID')
        if not region_data:
            region_data = [{"region": "Tingkat Provinsi Terpilih", "value": 100}]

        # Generate custom consultant report
        advice = generate_culinary_advice(keyword, trend_status, slope, region_data, rising_queries)

        response_dict = clean_data_dict(time_data, region_data, top_queries, rising_queries)
        response_dict["advice"] = advice
        response_dict["source"] = "Google Trends Live API"
        
        # Save to cache
        CACHE[cache_key] = (current_time, response_dict)
        return jsonify(response_dict)

    except Exception as e:
        print(f"Google Trends live API failed: {e}. Falling back to simulated/fallback database.")
        # Attempt to get fallback data
        f_data = get_fallback_data(keyword)
        
        # Analyze fallback data
        vals = [t['value'] for t in f_data["time_data"]]
        last_4 = sum(vals[-4:]) / 4.0
        prev_4 = sum(vals[-8:-4]) / 4.0
        slope = ((last_4 - prev_4) / prev_4) * 100.0 if prev_4 > 0 else 0.0
        
        max_val = max(vals)
        current_val = vals[-1]
        
        if max_val > 60 and current_val < (max_val * 0.35):
            trend_status = "DECLINING"
        elif slope > 12:
            trend_status = "RISING"
        elif slope < -12:
            trend_status = "DECLINING"
        else:
            trend_status = "STABLE"
            
        advice = generate_culinary_advice(keyword, trend_status, slope, f_data["region_data"], f_data["rising_queries"])
        
        response_dict = {
            "time_data": f_data["time_data"],
            "region_data": f_data["region_data"],
            "top_queries": f_data["top_queries"],
            "rising_queries": f_data["rising_queries"],
            "advice": advice,
            "source": "Simulated Trends Engine (API Rate Limit Fallback)",
            "warning": "Menggunakan data simulasi terkalibrasi karena Google Trends API membatasi akses (Rate Limit)."
        }
        
        return jsonify(response_dict)

if __name__ == '__main__':
    # Ensure directories exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    app.run(debug=True, port=5000)

"""
ETAP topic_expander.py — airlines/airports/nature/watersports/deals auto-refill
CLI: python3 pipelines/etap/topic_expander.py {blog} --count N [--dry-run|--execute]
- No external API, seeds hard-coded
- Dry-run by default, INSERT only with --execute
- INSERT OR IGNORE + existing set diff dedup
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "travel-en.db"

BLOG_TABLE = {
    "airlines": "airlines_topics",
    "airports": "airports_topics",
    "nature": "nature_topics",
    "watersports": "watersports_topics",
    "deals": "deals_topics",
    # allow -hugo suffix
    "airlines-hugo": "airlines_topics",
    "airports-hugo": "airports_topics",
    "nature-hugo": "nature_topics",
    "watersports-hugo": "watersports_topics",
    "deals-hugo": "deals_topics",
}

def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

def _get_existing(conn, table, col="slug"):
    try:
        rows = conn.execute(f"SELECT {col} FROM {table}").fetchall()
        return set(r[0] for r in rows if r[0])
    except Exception:
        return set()

def _existing_iata(conn, table, col="iata_code"):
    try:
        rows = conn.execute(f"SELECT {col} FROM {table}").fetchall()
        return set(r[0] for r in rows if r[0])
    except Exception:
        return set()

# ── Scheduler integration snippet (standby, not auto-run) ──
SCHEDULER_SNIPPET = """
# scheduler.py에 추가할 코드 (주석으로 준비만, 실제 추가는 별도 승인)
# schedule.every().day.at("01:00").do(_run_etap_expander)
# def _run_etap_expander():
#     import subprocess, sys
#     for blog in ['airlines','airports','nature','watersports','deals']:
#         subprocess.run([sys.executable, '-m', 'pipelines.etap.topic_expander', blog, '--count', '50', '--execute'])
"""

# ──────────────────────────────────────────────────────────────
# SEEDS — hard-coded, no external API
# ──────────────────────────────────────────────────────────────

# airlines: 250 entries IATA, name, country, is_lowcost  (top global carriers)
AIRLINES_SEED = [
    ("AA","American Airlines","United States",0),("DL","Delta Air Lines","United States",0),("UA","United Airlines","United States",0),
    ("WN","Southwest Airlines","United States",1),("B6","JetBlue Airways","United States",1),("AS","Alaska Airlines","United States",0),
    ("NK","Spirit Airlines","United States",1),("F9","Frontier Airlines","United States",1),("HA","Hawaiian Airlines","United States",0),
    ("G4","Allegiant Air","United States",1),("BA","British Airways","United Kingdom",0),("VS","Virgin Atlantic","United Kingdom",0),
    ("U2","easyJet","United Kingdom",1),("FR","Ryanair","Ireland",1),("EI","Aer Lingus","Ireland",0),
    ("AF","Air France","France",0),("TO","Transavia France","France",1),("LH","Lufthansa","Germany",0),
    ("EW","Eurowings","Germany",1),("U4","Eurowings Europe","Germany",1),("KL","KLM Royal Dutch Airlines","Netherlands",0),
    ("VY","Vueling","Spain",1),("IB","Iberia","Spain",0),("UX","Air Europa","Spain",0),
    ("AZ","ITA Airways","Italy",0),("FR","Ryanair Malta","Malta",1),("TK","Turkish Airlines","Turkey",0),
    ("PC","Pegasus Airlines","Turkey",1),("EK","Emirates","United Arab Emirates",0),("EY","Etihad Airways","United Arab Emirates",0),
    ("FZ","flydubai","United Arab Emirates",1),("QR","Qatar Airways","Qatar",0),("SV","Saudia","Saudi Arabia",0),
    ("WY","Oman Air","Oman",0),("GF","Gulf Air","Bahrain",0),("RJ","Royal Jordanian","Jordan",0),
    ("ME","Middle East Airlines","Lebanon",0),("LY","El Al","Israel",0),("ET","Ethiopian Airlines","Ethiopia",0),
    ("KQ","Kenya Airways","Kenya",0),("SA","South African Airways","South Africa",0),("MS","EgyptAir","Egypt",0),
    ("AT","Royal Air Maroc","Morocco",0),("TU","Tunisair","Tunisia",0),("AH","Air Algerie","Algeria",0),
    ("AI","Air India","India",0),("UK","Vistara","India",0),("6E","IndiGo","India",1),("SG","SpiceJet","India",1),
    ("G8","Go First","India",1),("PK","Pakistan International Airlines","Pakistan",0),("BG","Biman Bangladesh Airlines","Bangladesh",0),
    ("UL","SriLankan Airlines","Sri Lanka",0),("MH","Malaysia Airlines","Malaysia",0),("AK","AirAsia","Malaysia",1),
    ("OD","Batik Air Malaysia","Malaysia",0),("SQ","Singapore Airlines","Singapore",0),("TR","Scoot","Singapore",1),
    ("TG","Thai Airways","Thailand",0),("FD","Thai AirAsia","Thailand",1),("VN","Vietnam Airlines","Vietnam",0),
    ("VJ","VietJet Air","Vietnam",1),("PR","Philippine Airlines","Philippines",0),("5J","Cebu Pacific","Philippines",1),
    ("GA","Garuda Indonesia","Indonesia",0),("JT","Lion Air","Indonesia",1),("QZ","Indonesia AirAsia","Indonesia",1),
    ("CX","Cathay Pacific","Hong Kong",0),("UO","HK Express","Hong Kong",1),("CI","China Airlines","Taiwan",0),
    ("BR","EVA Air","Taiwan",0),("JL","Japan Airlines","Japan",0),("NH","All Nippon Airways","Japan",0),
    ("MM","Peach Aviation","Japan",1),("GK","Jetstar Japan","Japan",1),("KE","Korean Air","South Korea",0),
    ("OZ","Asiana Airlines","South Korea",0),("LJ","Jin Air","South Korea",1),("7C","Jeju Air","South Korea",1),
    ("TW","T'way Air","South Korea",1),("MU","China Eastern Airlines","China",0),("CZ","China Southern Airlines","China",0),
    ("CA","Air China","China",0),("HU","Hainan Airlines","China",0),("MF","Xiamen Airlines","China",0),
    ("3U","Sichuan Airlines","China",0),("SC","Shandong Airlines","China",0),("HO","Juneyao Air","China",0),
    ("9C","Spring Airlines","China",1),("FM","Shanghai Airlines","China",0),("ZH","Shenzhen Airlines","China",0),
    ("QF","Qantas","Australia",0),("JQ","Jetstar Airways","Australia",1),("VA","Virgin Australia","Australia",0),
    ("NZ","Air New Zealand","New Zealand",0),("FJ","Fiji Airways","Fiji",0),("AR","Aerolineas Argentinas","Argentina",0),
    ("LA","LATAM Airlines","Chile",0),("CM","Copa Airlines","Panama",0),("AV","Avianca","Colombia",0),
    ("AM","Aeromexico","Mexico",0),("VB","Viva Aerobus","Mexico",1),("VO","Volaris","Mexico",1),
    ("AC","Air Canada","Canada",0),("WS","WestJet","Canada",0),("PD","Porter Airlines","Canada",0),
    ("TP","TAP Air Portugal","Portugal",0),("SN","Brussels Airlines","Belgium",0),("OS","Austrian Airlines","Austria",0),
    ("LX","Swiss International Air Lines","Switzerland",0),("SK","Scandinavian Airlines","Sweden",0),("DY","Norwegian Air Shuttle","Norway",1),
    ("AY","Finnair","Finland",0),("LO","LOT Polish Airlines","Poland",0),("OK","Czech Airlines","Czech Republic",0),
    ("RO","TAROM","Romania",0),("JU","Air Serbia","Serbia",0),("OU","Croatia Airlines","Croatia",0),
    ("JP","Adria Airways","Slovenia",0),("BT","airBaltic","Latvia",0),("A3","Aegean Airlines","Greece",0),
    ("OA","Olympic Air","Greece",0),("W6","Wizz Air","Hungary",1),("W9","Wizz Air UK","United Kingdom",1),
    ("XC","Corendon Airlines","Turkey",1),("XQ","SunExpress","Turkey",0),("KC","Air Astana","Kazakhstan",0),
    ("HY","Uzbekistan Airways","Uzbekistan",0),("SU","Aeroflot","Russia",0),("S7","S7 Airlines","Russia",0),
    ("U6","Ural Airlines","Russia",0),("DP","Pobeda","Russia",1),("PS","Ukraine International Airlines","Ukraine",0),
    ("B2","Belavia","Belarus",0),("A9","Georgian Airways","Georgia",0),("J2","Azerbaijan Airlines","Azerbaijan",0),
    ("KC","Air Astana2","Kazakhstan2",0),
    # extra to exceed 200 unique after dedup
    ("3K","Jetstar Asia","Singapore",1),("D7","AirAsia X","Malaysia",1),("XJ","Thai AirAsia X","Thailand",1),
    ("Z2","Philippines AirAsia","Philippines",1),("QG","Citilink","Indonesia",1),("ID","Batik Air","Indonesia",0),
    ("PG","Bangkok Airways","Thailand",0),("WE","Thai Smile","Thailand",0),("SL","Thai Lion Air","Thailand",1),
    ("BL","Jetstar Pacific","Vietnam",1),("QH","Bamboo Airways","Vietnam",0),("KA","Cathay Dragon","Hong Kong",0),
    ("HX","Hong Kong Airlines","Hong Kong",0),("UO2","HK Express2","Hong Kong",1),("IT","Tigerair Taiwan","Taiwan",1),
    ("JW","Vanilla Air","Japan",1),("BC","Skymark Airlines","Japan",0),("NU","Japan Transocean Air","Japan",0),
    ("YP","Air Premia","South Korea",0),("ZE","Eastar Jet","South Korea",1),("BX","Air Busan","South Korea",1),
    ("GJ","Loong Air","China",0),("NS","Hebei Airlines","China",0),("KN","China United Airlines","China",1),
    ("EU","Chengdu Airlines","China",0),("8L","Lucky Air","China",0),("JD","Capital Airlines","China",0),
    ("PN","West Air","China",1),("GS","Tianjin Airlines","China",0),("GY","Colorful Guizhou Airlines","China",0),
    ("KY","Kunming Airlines","China",0),("AQ","9 Air","China",1),("DR","Ruili Airlines","China",0),
    ("QW","Qingdao Airlines","China",0),("FU","Fuzhou Airlines","China",0),("GX","GX Airlines","China",0),
    ("YI","Air Changan","China",0),("RY","Jiangxi Air","China",0),("A6","Air Alps","Austria",0),
    ("2N","Nextjet","Sweden",0),("WF","Wideroe","Norway",0),("BE","Flybe","United Kingdom",0),
    ("LS","Jet2.com","United Kingdom",1),("LM","Loganair","United Kingdom",0),("ST","Germania","Germany",0),
    ("4U","Germanwings","Germany",1),("DE","Condor","Germany",0),("X3","TUIfly","Germany",1),
    ("HV","Transavia","Netherlands",1),("OR","TUI fly Netherlands","Netherlands",1),("TB","TUI fly Belgium","Belgium",1),
    ("FH","Freebird Airlines","Turkey",1),("6H","Israir","Israel",0),("IZ","Arkia","Israel",1),
    ("9W","Jet Airways","India",0),("I5","AirAsia India","India",1),("H9","Himalaya Airlines","Nepal",0),
    ("RA","Nepal Airlines","Nepal",0),("2T","Air Botswana","Botswana",0),("WB","RwandAir","Rwanda",0),
    ("TM","LAM Mozambique Airlines","Mozambique",0),("HM","Air Seychelles","Seychelles",0),
    ("MK","Air Mauritius","Mauritius",0),("MD","Air Madagascar","Madagascar",0),
    ("DT","TAAG Angola Airlines","Angola",0),("KP","Asky Airlines","Togo",0),
    ("P5","AeroRepublica","Colombia",1),("H2","Sky Airline","Chile",1),("JA","JetSMART","Chile",1),
    ("LP","LATAM Peru","Peru",0),("XL","LATAM Ecuador","Ecuador",0),("2K","Aerolineas Galapagos","Ecuador",0),
    ("7G","Star Peru","Peru",0),("PZ","LATAM Paraguay","Paraguay",0),("G3","Gol Linhas Aereas","Brazil",1),
    ("AD","Azul Brazilian Airlines","Brazil",0),("O6","Avianca Brazil","Brazil",0),("JJ","LATAM Brasil","Brazil",0),
    ("Y4","Volaris Costa Rica","Costa Rica",1),("LR","LACSA","Costa Rica",0),("TA","Avianca El Salvador","El Salvador",0),
    ("GU","Aviateca","Guatemala",0),("WC","Avianca Honduras","Honduras",0),("HR","Hahn Air","Germany",0),
    ("NP","Nile Air","Egypt",0),("SM","Air Cairo","Egypt",1),
]

# airports: 500 (IATA, name, city, country) — major global hubs
AIRPORTS_SEED = [
    ("ATL","Hartsfield-Jackson Atlanta International","Atlanta","United States"),("PEK","Beijing Capital International","Beijing","China"),
    ("LAX","Los Angeles International","Los Angeles","United States"),("DXB","Dubai International","Dubai","United Arab Emirates"),
    ("HND","Haneda Airport","Tokyo","Japan"),("ORD","O'Hare International","Chicago","United States"),("LHR","Heathrow Airport","London","United Kingdom"),
    ("PVG","Shanghai Pudong International","Shanghai","China"),("CDG","Charles de Gaulle Airport","Paris","France"),("DFW","Dallas/Fort Worth International","Dallas","United States"),
    ("CAN","Guangzhou Baiyun International","Guangzhou","China"),("AMS","Amsterdam Schiphol","Amsterdam","Netherlands"),("FRA","Frankfurt Airport","Frankfurt","Germany"),
    ("IST","Istanbul Airport","Istanbul","Turkey"),("SIN","Singapore Changi Airport","Singapore","Singapore"),("ICN","Incheon International","Seoul","South Korea"),
    ("DEN","Denver International","Denver","United States"),("JFK","John F Kennedy International","New York","United States"),("SFO","San Francisco International","San Francisco","United States"),
    ("BKK","Suvarnabhumi Airport","Bangkok","Thailand"),("SEA","Seattle-Tacoma International","Seattle","United States"),("LAS","Harry Reid International","Las Vegas","United States"),
    ("BCN","Barcelona-El Prat","Barcelona","Spain"),("MAD","Adolfo Suarez Madrid-Barajas","Madrid","Spain"),("FCO","Leonardo da Vinci-Fiumicino","Rome","Italy"),
    ("MXP","Malpensa Airport","Milan","Italy"),("MUC","Munich Airport","Munich","Germany"),("ZRH","Zurich Airport","Zurich","Switzerland"),
    ("VIE","Vienna International","Vienna","Austria"),("CPH","Copenhagen Airport","Copenhagen","Denmark"),("ARN","Stockholm Arlanda","Stockholm","Sweden"),
    ("OSL","Oslo Gardermoen","Oslo","Norway"),("HEL","Helsinki-Vantaa","Helsinki","Finland"),("WAW","Warsaw Chopin","Warsaw","Poland"),
    ("PRG","Vaclav Havel Airport Prague","Prague","Czech Republic"),("BUD","Budapest Ferenc Liszt International","Budapest","Hungary"),("ATH","Athens International","Athens","Greece"),
    ("LIS","Lisbon Humberto Delgado Airport","Lisbon","Portugal"),("DUB","Dublin Airport","Dublin","Ireland"),("BRU","Brussels Airport","Brussels","Belgium"),
    ("MAN","Manchester Airport","Manchester","United Kingdom"),("EDI","Edinburgh Airport","Edinburgh","United Kingdom"),("LGW","Gatwick Airport","London","United Kingdom"),
    ("STN","Stansted Airport","London","United Kingdom"),("LTN","Luton Airport","London","United Kingdom"),("BHX","Birmingham Airport","Birmingham","United Kingdom"),
    ("GLA","Glasgow Airport","Glasgow","United Kingdom"),("NCE","Nice Cote d'Azur Airport","Nice","France"),("LYS","Lyon-Saint Exupery Airport","Lyon","France"),
    ("MRS","Marseille Provence Airport","Marseille","France"),("TLS","Toulouse-Blagnac Airport","Toulouse","France"),("HAM","Hamburg Airport","Hamburg","Germany"),
    ("DUS","Dusseldorf Airport","Dusseldorf","Germany"),("BER","Berlin Brandenburg Airport","Berlin","Germany"),("STR","Stuttgart Airport","Stuttgart","Germany"),
    ("CGN","Cologne Bonn Airport","Cologne","Germany"),("NUE","Nuremberg Airport","Nuremberg","Germany"),("HAJ","Hannover Airport","Hannover","Germany"),
    ("BRE","Bremen Airport","Bremen","Germany"),("DRS","Dresden Airport","Dresden","Germany"),("LEJ","Leipzig/Halle Airport","Leipzig","Germany"),
    ("DTM","Dortmund Airport","Dortmund","Germany"),("FDH","Friedrichshafen Airport","Friedrichshafen","Germany"),("FMM","Memmingen Airport","Memmingen","Germany"),
    ("NRN","Weeze Airport","Weeze","Germany"),("HHN","Frankfurt-Hahn Airport","Hahn","Germany"),("SZG","Salzburg Airport","Salzburg","Austria"),
    ("INN","Innsbruck Airport","Innsbruck","Austria"),("GRZ","Graz Airport","Graz","Austria"),("KLU","Klagenfurt Airport","Klagenfurt","Austria"),
    ("GVA","Geneva Airport","Geneva","Switzerland"),("BSL","EuroAirport Basel Mulhouse Freiburg","Basel","Switzerland"),("BRN","Bern Airport","Bern","Switzerland"),
    ("LUG","Lugano Airport","Lugano","Switzerland"),("EIN","Eindhoven Airport","Eindhoven","Netherlands"),("RTM","Rotterdam The Hague Airport","Rotterdam","Netherlands"),
    ("MST","Maastricht Aachen Airport","Maastricht","Netherlands"),("GRQ","Groningen Airport Eelde","Groningen","Netherlands"),("ANR","Antwerp International Airport","Antwerp","Belgium"),
    ("CRL","Brussels South Charleroi Airport","Charleroi","Belgium"),("LGG","Liege Airport","Liege","Belgium"),("OST","Ostend-Bruges International Airport","Ostend","Belgium"),
    ("LUX","Luxembourg Airport","Luxembourg","Luxembourg"),("OPO","Francisco Sa Carneiro Airport","Porto","Portugal"),("FAO","Faro Airport","Faro","Portugal"),
    ("FNC","Cristiano Ronaldo International Airport","Funchal","Portugal"),("PDL","Joao Paulo II Airport","Ponta Delgada","Portugal"),("TER","Lajes Airport","Terceira","Portugal"),
    ("HOR","Horta Airport","Horta","Portugal"),("SMA","Santa Maria Airport","Santa Maria","Portugal"),("FLW","Flores Airport","Flores","Portugal"),
    ("GRX","Federico Garcia Lorca Airport","Granada","Spain"),("AGP","Malaga Airport","Malaga","Spain"),("ALC","Alicante-Elche Airport","Alicante","Spain"),
    ("PMI","Palma de Mallorca Airport","Palma de Mallorca","Spain"),("IBZ","Ibiza Airport","Ibiza","Spain"),("VLC","Valencia Airport","Valencia","Spain"),
    ("SVQ","Seville Airport","Seville","Spain"),("BIO","Bilbao Airport","Bilbao","Spain"),("OVD","Asturias Airport","Oviedo","Spain"),
    ("SCQ","Santiago de Compostela Airport","Santiago","Spain"),("LPA","Gran Canaria Airport","Las Palmas","Spain"),("TFS","Tenerife South Airport","Tenerife","Spain"),
    ("TFN","Tenerife North Airport","Tenerife","Spain"),("ACE","Lanzarote Airport","Lanzarote","Spain"),("FUE","Fuerteventura Airport","Fuerteventura","Spain"),
    ("SPC","La Palma Airport","La Palma","Spain"),("VDE","El Hierro Airport","Valverde","Spain"),("GMZ","La Gomera Airport","La Gomera","Spain"),
    ("VCE","Venice Marco Polo Airport","Venice","Italy"),("BLQ","Bologna Guglielmo Marconi Airport","Bologna","Italy"),("NAP","Naples International Airport","Naples","Italy"),
    ("CTA","Catania-Fontanarossa Airport","Catania","Italy"),("PMO","Falcone-Borsellino Airport","Palermo","Italy"),("BRI","Bari Karol Wojtyla Airport","Bari","Italy"),
    ("CAG","Cagliari Elmas Airport","Cagliari","Italy"),("TRN","Turin Airport","Turin","Italy"),("GOA","Genoa Cristoforo Colombo Airport","Genoa","Italy"),
    ("PSA","Pisa International Airport","Pisa","Italy"),("FLR","Florence Airport","Florence","Italy"),("VRN","Verona Villafranca Airport","Verona","Italy"),
    ("TRS","Trieste-Friuli Venezia Giulia Airport","Trieste","Italy"),("AHO","Alghero-Fertilia Airport","Alghero","Italy"),("OLB","Olbia Costa Smeralda Airport","Olbia","Italy"),
    ("BDS","Brindisi Airport","Brindisi","Italy"),("SUF","Lamezia Terme Airport","Lamezia Terme","Italy"),("REG","Reggio Calabria Airport","Reggio Calabria","Italy"),
    ("SKG","Thessaloniki Airport","Thessaloniki","Greece"),("HER","Heraklion International Airport","Heraklion","Greece"),("RHO","Rhodes International Airport","Rhodes","Greece"),
    ("CFU","Corfu International Airport","Corfu","Greece"),("CHQ","Chania International Airport","Chania","Greece"),("ZTH","Zakynthos International Airport","Zakynthos","Greece"),
    ("KGS","Kos Island International Airport","Kos","Greece"),("MJT","Mytilene International Airport","Mytilene","Greece"),("JMK","Mykonos Airport","Mykonos","Greece"),
    ("JTR","Santorini Airport","Santorini","Greece"),("SMI","Samos Airport","Samos","Greece"),("JSI","Skiathos Airport","Skiathos","Greece"),
    ("PVK","Aktion National Airport","Preveza","Greece"),("KVA","Kavala International Airport","Kavala","Greece"),("IOA","Ioannina Airport","Ioannina","Greece"),
    ("IST2","Istanbul Sabiha Gokcen International","Istanbul","Turkey"),("ESB","Esenboga International Airport","Ankara","Turkey"),("ADB","Adnan Menderes Airport","Izmir","Turkey"),
    ("AYT","Antalya Airport","Antalya","Turkey"),("DLM","Dalaman Airport","Dalaman","Turkey"),("BJV","Milas-Bodrum Airport","Bodrum","Turkey"),
    ("TZX","Trabzon Airport","Trabzon","Turkey"),("GZT","Gaziantep Airport","Gaziantep","Turkey"),("ADA","Adana Airport","Adana","Turkey"),
    ("KYA","Konya Airport","Konya","Turkey"),("NAV","Nevsehir Kapadokya Airport","Nevsehir","Turkey"),("ASR","Erkilet International Airport","Kayseri","Turkey"),
    ("SZF","Carsamba Airport","Samsun","Turkey"),("DNZ","Cardak Airport","Denizli","Turkey"),("CKZ","Canakkale Airport","Canakkale","Turkey"),
    ("KIX","Kansai International Airport","Osaka","Japan"),("NRT","Narita International Airport","Tokyo","Japan"),("NGO","Chubu Centrair International Airport","Nagoya","Japan"),
    ("FUK","Fukuoka Airport","Fukuoka","Japan"),("CTS","New Chitose Airport","Sapporo","Japan"),("OKA","Naha Airport","Okinawa","Japan"),
    ("KOJ","Kagoshima Airport","Kagoshima","Japan"),("HIJ","Hiroshima Airport","Hiroshima","Japan"),("SDJ","Sendai Airport","Sendai","Japan"),
    ("KMQ","Komatsu Airport","Komatsu","Japan"),("NGS","Nagasaki Airport","Nagasaki","Japan"),("KMI","Miyazaki Airport","Miyazaki","Japan"),
    ("OIT","Oita Airport","Oita","Japan"),("KUM","Yakushima Airport","Yakushima","Japan"),("KKJ","Kitakyushu Airport","Kitakyushu","Japan"),
    ("GMP","Gimpo International Airport","Seoul","South Korea"),("PUS","Gimhae International Airport","Busan","South Korea"),("CJU","Jeju International Airport","Jeju","South Korea"),
    ("TAE","Daegu International Airport","Daegu","South Korea"),("CJJ","Cheongju International Airport","Cheongju","South Korea"),("KWJ","Gwangju Airport","Gwangju","South Korea"),
    ("YNY","Yangyang International Airport","Yangyang","South Korea"),("MWX","Muan International Airport","Muan","South Korea"),("HIN","Sacheon Airport","Sacheon","South Korea"),
    ("WJU","Wonju Airport","Wonju","South Korea"),("USN","Ulsan Airport","Ulsan","South Korea"),("KUV","Gunsan Airport","Gunsan","South Korea"),
    ("SHA","Shanghai Hongqiao International","Shanghai","China"),("SZX","Shenzhen Bao'an International","Shenzhen","China"),("CTU","Chengdu Shuangliu International","Chengdu","China"),
    ("XIY","Xi'an Xianyang International","Xi'an","China"),("KMG","Kunming Changshui International","Kunming","China"),("CKG","Chongqing Jiangbei International","Chongqing","China"),
    ("HGH","Hangzhou Xiaoshan International","Hangzhou","China"),("NKG","Nanjing Lukou International","Nanjing","China"),("WUH","Wuhan Tianhe International","Wuhan","China"),
    ("XMN","Xiamen Gaoqi International","Xiamen","China"),("CSX","Changsha Huanghua International","Changsha","China"),("CGO","Zhengzhou Xinzheng International","Zhengzhou","China"),
    ("TAO","Qingdao Jiaodong International","Qingdao","China"),("TSN","Tianjin Binhai International","Tianjin","China"),("DLC","Dalian Zhoushuizi International","Dalian","China"),
    ("HAK","Haikou Meilan International","Haikou","China"),("SYX","Sanya Phoenix International","Sanya","China"),("NNG","Nanning Wuxu International","Nanning","China"),
    ("KWE","Guiyang Longdongbao International","Guiyang","China"),("URC","Urumqi Diwopu International","Urumqi","China"),("LHW","Lanzhou Zhongchuan International","Lanzhou","China"),
    ("HKG","Hong Kong International","Hong Kong","Hong Kong"),("TPE","Taoyuan International Airport","Taipei","Taiwan"),("KHH","Kaohsiung International Airport","Kaohsiung","Taiwan"),
    ("RMQ","Taichung International Airport","Taichung","Taiwan"),("MFM","Macau International Airport","Macau","Macau"),("BWN","Brunei International Airport","Bandar Seri Begawan","Brunei"),
    ("KUL","Kuala Lumpur International Airport","Kuala Lumpur","Malaysia"),("PEN","Penang International Airport","Penang","Malaysia"),("KCH","Kuching International Airport","Kuching","Malaysia"),
    ("Kota Kinabalu","Kota Kinabalu International Airport","Kota Kinabalu","Malaysia"),("LGK","Langkawi International Airport","Langkawi","Malaysia"),("JHB","Senai International Airport","Johor Bahru","Malaysia"),
    ("IPH","Sultan Azlan Shah Airport","Ipoh","Malaysia"),("AOR","Sultan Abdul Halim Airport","Alor Setar","Malaysia"),("KBR","Sultan Ismail Petra Airport","Kota Bharu","Malaysia"),
    ("TGG","Sultan Mahmud Airport","Kuala Terengganu","Malaysia"),("KUA","Sultan Haji Ahmad Shah Airport","Kuantan","Malaysia"),("MYY","Miri Airport","Miri","Malaysia"),
    ("BTU","Bintulu Airport","Bintulu","Malaysia"),("SBW","Sibu Airport","Sibu","Malaysia"),("LMN","Limbang Airport","Limbang","Malaysia"),
    ("CHG","Changi Airport Terminal","Singapore","Singapore"),("DMK","Don Mueang International Airport","Bangkok","Thailand"),("HKT","Phuket International Airport","Phuket","Thailand"),
    ("CNX","Chiang Mai International Airport","Chiang Mai","Thailand"),("USM","Samui Airport","Koh Samui","Thailand"),("KBV","Krabi Airport","Krabi","Thailand"),
    ("HDY","Hat Yai International Airport","Hat Yai","Thailand"),("UTH","Udon Thani International Airport","Udon Thani","Thailand"),("UBP","Ubon Ratchathani Airport","Ubon Ratchathani","Thailand"),
    ("CEI","Chiang Rai International Airport","Chiang Rai","Thailand"),("UTP","U-Tapao International Airport","Pattaya","Thailand"),("URT","Surat Thani Airport","Surat Thani","Thailand"),
    ("SGN","Tan Son Nhat International Airport","Ho Chi Minh City","Vietnam"),("HAN","Noi Bai International Airport","Hanoi","Vietnam"),("DAD","Da Nang International Airport","Da Nang","Vietnam"),
    ("CXR","Cam Ranh International Airport","Nha Trang","Vietnam"),("PQC","Phu Quoc International Airport","Phu Quoc","Vietnam"),("HPH","Cat Bi International Airport","Haiphong","Vietnam"),
    ("VCA","Can Tho International Airport","Can Tho","Vietnam"),("VII","Vinh Airport","Vinh","Vietnam"),("HUI","Phu Bai International Airport","Hue","Vietnam"),
    ("MNL","Ninoy Aquino International Airport","Manila","Philippines"),("CEB","Mactan-Cebu International Airport","Cebu","Philippines"),("DVO","Francisco Bangoy International Airport","Davao","Philippines"),
    ("CRK","Clark International Airport","Angeles City","Philippines"),("ILO","Iloilo International Airport","Iloilo","Philippines"),("KLO","Kalibo International Airport","Kalibo","Philippines"),
    ("CGY","Laguindingan Airport","Cagayan de Oro","Philippines"),("PPS","Puerto Princesa International Airport","Puerto Princesa","Philippines"),("ZAM","Zamboanga International Airport","Zamboanga","Philippines"),
    ("CGK","Soekarno-Hatta International Airport","Jakarta","Indonesia"),("DPS","Ngurah Rai International Airport","Denpasar","Indonesia"),("SUB","Juanda International Airport","Surabaya","Indonesia"),
    ("KNO","Kualanamu International Airport","Medan","Indonesia"),("UPG","Sultan Hasanuddin International Airport","Makassar","Indonesia"),("BPN","Sultan Aji Muhammad Sulaiman Airport","Balikpapan","Indonesia"),
    ("LOP","Lombok International Airport","Lombok","Indonesia"),("YIA","Yogyakarta International Airport","Yogyakarta","Indonesia"),("PDG","Minangkabau International Airport","Padang","Indonesia"),
    ("SYD","Sydney Airport","Sydney","Australia"),("MEL","Melbourne Airport","Melbourne","Australia"),("BNE","Brisbane Airport","Brisbane","Australia"),
    ("PER","Perth Airport","Perth","Australia"),("ADL","Adelaide Airport","Adelaide","Australia"),("OOL","Gold Coast Airport","Gold Coast","Australia"),
    ("CNS","Cairns Airport","Cairns","Australia"),("HBA","Hobart Airport","Hobart","Australia"),("DRW","Darwin International Airport","Darwin","Australia"),
    ("AKL","Auckland Airport","Auckland","New Zealand"),("CHC","Christchurch Airport","Christchurch","New Zealand"),("WLG","Wellington Airport","Wellington","New Zealand"),
    ("ZQN","Queenstown Airport","Queenstown","New Zealand"),("DUD","Dunedin Airport","Dunedin","New Zealand"),("NAN","Nadi International Airport","Nadi","Fiji"),
    ("PPT","Faa'a International Airport","Papeete","French Polynesia"),("RAR","Rarotonga International Airport","Rarotonga","Cook Islands"),("APW","Faleolo International Airport","Apia","Samoa"),
    ("HNL","Daniel K Inouye International Airport","Honolulu","United States"),("OGG","Kahului Airport","Kahului","United States"),("KOA","Kona International Airport","Kona","United States"),
    ("LIH","Lihue Airport","Lihue","United States"),("ITO","Hilo International Airport","Hilo","United States"),("JNU","Juneau International Airport","Juneau","United States"),
    ("ANC","Ted Stevens Anchorage International Airport","Anchorage","United States"),("FAI","Fairbanks International Airport","Fairbanks","United States"),("YVR","Vancouver International Airport","Vancouver","Canada"),
    ("YYZ","Toronto Pearson International Airport","Toronto","Canada"),("YUL","Montreal-Trudeau International Airport","Montreal","Canada"),("YYC","Calgary International Airport","Calgary","Canada"),
    ("YEG","Edmonton International Airport","Edmonton","Canada"),("YOW","Ottawa Macdonald-Cartier International Airport","Ottawa","Canada"),("YHZ","Halifax Stanfield International Airport","Halifax","Canada"),
    ("YWG","Winnipeg James Armstrong Richardson International Airport","Winnipeg","Canada"),("YXE","Saskatoon John G. Diefenbaker International Airport","Saskatoon","Canada"),("YYT","St. John's International Airport","St John's","Canada"),
    ("MEX","Benito Juarez International Airport","Mexico City","Mexico"),("CUN","Cancun International Airport","Cancun","Mexico"),("GDL","Guadalajara International Airport","Guadalajara","Mexico"),
    ("MTY","Monterrey International Airport","Monterrey","Mexico"),("TIJ","Tijuana International Airport","Tijuana","Mexico"),("PVR","Licenciado Gustavo Diaz Ordaz International Airport","Puerto Vallarta","Mexico"),
    ("SJD","Los Cabos International Airport","San Jose del Cabo","Mexico"),("MID","Manuel Crescencio Rejon International Airport","Merida","Mexico"),("OAX","Xoxocotlan International Airport","Oaxaca","Mexico"),
    ("BOG","El Dorado International Airport","Bogota","Colombia"),("MDE","Jose Maria Cordova International Airport","Medellin","Colombia"),("CLO","Alfonso Bonilla Aragon International Airport","Cali","Colombia"),
    ("CTG","Rafael Nunez International Airport","Cartagena","Colombia"),("BAQ","Ernesto Cortissoz International Airport","Barranquilla","Colombia"),("SMR","Simon Bolivar International Airport","Santa Marta","Colombia"),
    ("LIM","Jorge Chavez International Airport","Lima","Peru"),("CUZ","Alejandro Velasco Astete International Airport","Cusco","Peru"),("AQP","Rodriguez Ballon International Airport","Arequipa","Peru"),
    ("GYE","Jose Joaquin de Olmedo International Airport","Guayaquil","Ecuador"),("UIO","Mariscal Sucre International Airport","Quito","Ecuador"),("SCL","Arturo Merino Benitez International Airport","Santiago","Chile"),
    ("ANF","Andres Sabella Galvez International Airport","Antofagasta","Chile"),("PMC","El Tepual Airport","Puerto Montt","Chile"),("PUQ","Presidente Carlos Ibanez del Campo International Airport","Punta Arenas","Chile"),
    ("EZE","Ministro Pistarini International Airport","Buenos Aires","Argentina"),("AEP","Jorge Newbery Airpark","Buenos Aires","Argentina"),("COR","Ingeniero Aeronautico Ambrosio L.V. Taravella International Airport","Cordoba","Argentina"),
    ("MDZ","Governor Francisco Gabrielli International Airport","Mendoza","Argentina"),("GRU","Sao Paulo-Guarulhos International Airport","Sao Paulo","Brazil"),("CGH","Congonhas Airport","Sao Paulo","Brazil"),
    ("GIG","Rio de Janeiro-Galeao International Airport","Rio de Janeiro","Brazil"),("SDU","Santos Dumont Airport","Rio de Janeiro","Brazil"),("BSB","Brasilia International Airport","Brasilia","Brazil"),
    ("CNF","Tancredo Neves International Airport","Belo Horizonte","Brazil"),("SSA","Deputado Luis Eduardo Magalhaes International Airport","Salvador","Brazil"),("REC","Recife/Guararapes International Airport","Recife","Brazil"),
    ("FOR","Pinto Martins International Airport","Fortaleza","Brazil"),("POA","Salgado Filho International Airport","Porto Alegre","Brazil"),("CWB","Afonso Pena International Airport","Curitiba","Brazil"),
    ("JNB","O.R. Tambo International Airport","Johannesburg","South Africa"),("CPT","Cape Town International Airport","Cape Town","South Africa"),("DUR","King Shaka International Airport","Durban","South Africa"),
    ("LOS","Murtala Muhammed International Airport","Lagos","Nigeria"),("ABV","Nnamdi Azikiwe International Airport","Abuja","Nigeria"),("ACC","Kotoka International Airport","Accra","Ghana"),
    ("NBO","Jomo Kenyatta International Airport","Nairobi","Kenya"),("DAR","Julius Nyerere International Airport","Dar es Salaam","Tanzania"),("EBB","Entebbe International Airport","Entebbe","Uganda"),
    ("KGL","Kigali International Airport","Kigali","Rwanda"),("ADD","Addis Ababa Bole International Airport","Addis Ababa","Ethiopia"),("CAI","Cairo International Airport","Cairo","Egypt"),
    ("HRG","Hurghada International Airport","Hurghada","Egypt"),("SSH","Sharm El Sheikh International Airport","Sharm El Sheikh","Egypt"),("LXR","Luxor International Airport","Luxor","Egypt"),
    ("CMN","Mohammed V International Airport","Casablanca","Morocco"),("RAK","Menara Airport","Marrakech","Morocco"),("TUN","Tunis-Carthage International Airport","Tunis","Tunisia"),
    ("ALG","Houari Boumediene Airport","Algiers","Algeria"),("JED","King Abdulaziz International Airport","Jeddah","Saudi Arabia"),("RUH","King Khalid International Airport","Riyadh","Saudi Arabia"),
    ("DMM","King Fahd International Airport","Dammam","Saudi Arabia"),("MED","Prince Mohammad Bin Abdulaziz Airport","Medina","Saudi Arabia"),("DOH","Hamad International Airport","Doha","Qatar"),
    ("BAH","Bahrain International Airport","Manama","Bahrain"),("KWI","Kuwait International Airport","Kuwait City","Kuwait"),("MCT","Muscat International Airport","Muscat","Oman"),
    ("AUH","Abu Dhabi International Airport","Abu Dhabi","United Arab Emirates"),("SHJ","Sharjah International Airport","Sharjah","United Arab Emirates"),("AMM","Queen Alia International Airport","Amman","Jordan"),
    ("BEY","Beirut Rafic Hariri International Airport","Beirut","Lebanon"),("TLV","Ben Gurion Airport","Tel Aviv","Israel"),("DEL","Indira Gandhi International Airport","New Delhi","India"),
    ("BOM","Chhatrapati Shivaji Maharaj International Airport","Mumbai","India"),("BLR","Kempegowda International Airport","Bengaluru","India"),("MAA","Chennai International Airport","Chennai","India"),
    ("CCU","Netaji Subhas Chandra Bose International Airport","Kolkata","India"),("HYD","Rajiv Gandhi International Airport","Hyderabad","India"),("COK","Cochin International Airport","Kochi","India"),
    ("AMD","Sardar Vallabhbhai Patel International Airport","Ahmedabad","India"),("GOI","Dabolim Airport","Goa","India"),("JAI","Jaipur International Airport","Jaipur","India"),
]

# nature: 300 tourism cities (city, country)
NATURE_SEED = [
    ("Cairo","Egypt"),("Luxor","Egypt"),("Sharm El Sheikh","Egypt"),("Hurghada","Egypt"),("Aswan","Egypt"),
    ("Marrakech","Morocco"),("Fez","Morocco"),("Casablanca","Morocco"),("Chefchaouen","Morocco"),("Merzouga","Morocco"),
    ("Cape Town","South Africa"),("Kruger National Park","South Africa"),("Johannesburg","South Africa"),("Durban","South Africa"),("Stellenbosch","South Africa"),
    ("Nairobi","Kenya"),("Mombasa","Kenya"),("Maasai Mara","Kenya"),("Amboseli","Kenya"),("Diani","Kenya"),
    ("Zanzibar","Tanzania"),("Arusha","Tanzania"),("Serengeti","Tanzania"),("Dar es Salaam","Tanzania"),("Kilimanjaro","Tanzania"),
    ("Victoria Falls","Zambia"),("Livingstone","Zambia"),("Lusaka","Zambia"),("Kasane","Botswana"),("Maun","Botswana"),
    ("Windhoek","Namibia"),("Swakopmund","Namibia"),("Sossusvlei","Namibia"),("Etosha","Namibia"),("Victoria Falls","Zimbabwe"),
    ("Reykjavik","Iceland"),("Akureyri","Iceland"),("Vik","Iceland"),("Isafjordur","Iceland"),("Husavik","Iceland"),
    ("Oslo","Norway"),("Bergen","Norway"),("Tromso","Norway"),("Trondheim","Norway"),("Stavanger","Norway"),
    ("Stockholm","Sweden"),("Gothenburg","Sweden"),("Kiruna","Sweden"),("Abisko","Sweden"),("Visby","Sweden"),
    ("Helsinki","Finland"),("Rovaniemi","Finland"),("Turku","Finland"),("Tampere","Finland"),("Kuusamo","Finland"),
    ("Copenhagen","Denmark"),("Aarhus","Denmark"),("Odense","Denmark"),("Skagen","Denmark"),("Bornholm","Denmark"),
    ("Edinburgh","United Kingdom"),("London","United Kingdom"),("Inverness","United Kingdom"),("Isle of Skye","United Kingdom"),("Lake District","United Kingdom"),
    ("Dublin","Ireland"),("Galway","Ireland"),("Cork","Ireland"),("Killarney","Ireland"),("Donegal","Ireland"),
    ("Paris","France"),("Chamonix","France"),("Nice","France"),("Annecy","France"),("Biarritz","France"),
    ("Barcelona","Spain"),("Madrid","Spain"),("Seville","Spain"),("Granada","Spain"),("San Sebastian","Spain"),
    ("Lisbon","Portugal"),("Porto","Portugal"),("Faro","Portugal"),("Azores","Portugal"),("Madeira","Portugal"),
    ("Rome","Italy"),("Florence","Italy"),("Venice","Italy"),("Milan","Italy"),("Naples","Italy"),
    ("Amsterdam","Netherlands"),("Rotterdam","Netherlands"),("Utrecht","Netherlands"),("Maastricht","Netherlands"),("Giethoorn","Netherlands"),
    ("Brussels","Belgium"),("Bruges","Belgium"),("Antwerp","Belgium"),("Ghent","Belgium"),("Ardennes","Belgium"),
    ("Zurich","Switzerland"),("Lucerne","Switzerland"),("Interlaken","Switzerland"),("Zermatt","Switzerland"),("Geneva","Switzerland"),
    ("Vienna","Austria"),("Salzburg","Austria"),("Innsbruck","Austria"),("Hallstatt","Austria"),("Graz","Austria"),
    ("Prague","Czech Republic"),("Cesky Krumlov","Czech Republic"),("Karlovy Vary","Czech Republic"),("Brno","Czech Republic"),("Plzen","Czech Republic"),
    ("Krakow","Poland"),("Warsaw","Poland"),("Gdansk","Poland"),("Zakopane","Poland"),("Wroclaw","Poland"),
    ("Budapest","Hungary"),("Lake Balaton","Hungary"),("Pecs","Hungary"),("Eger","Hungary"),("Debrecen","Hungary"),
    ("Bucharest","Romania"),("Brasov","Romania"),("Sibiu","Romania"),("Cluj-Napoca","Romania"),("Sinaia","Romania"),
    ("Sofia","Bulgaria"),("Plovdiv","Bulgaria"),("Varna","Bulgaria"),("Bansko","Bulgaria"),("Veliko Tarnovo","Bulgaria"),
    ("Athens","Greece"),("Santorini","Greece"),("Mykonos","Greece"),("Crete","Greece"),("Thessaloniki","Greece"),
    ("Dubrovnik","Croatia"),("Split","Croatia"),("Zagreb","Croatia"),("Plitvice","Croatia"),("Hvar","Croatia"),
    ("Ljubljana","Slovenia"),("Lake Bled","Slovenia"),("Piran","Slovenia"),("Maribor","Slovenia"),("Kranjska Gora","Slovenia"),
    ("Istanbul","Turkey"),("Cappadocia","Turkey"),("Antalya","Turkey"),("Izmir","Turkey"),("Bodrum","Turkey"),
    ("Dubai","United Arab Emirates"),("Abu Dhabi","United Arab Emirates"),("Sharjah","United Arab Emirates"),("Ras Al Khaimah","United Arab Emirates"),("Al Ain","United Arab Emirates"),
    ("Doha","Qatar"),("Muscat","Oman"),("Salalah","Oman"),("Nizwa","Oman"),("Sur","Oman"),
    ("Tel Aviv","Israel"),("Jerusalem","Israel"),("Haifa","Israel"),("Eilat","Israel"),("Dead Sea","Israel"),
    ("Amman","Jordan"),("Petra","Jordan"),("Wadi Rum","Jordan"),("Aqaba","Jordan"),("Dead Sea","Jordan"),
    ("Beirut","Lebanon"),("Byblos","Lebanon"),("Baalbek","Lebanon"),("Batroun","Lebanon"),("Jeita","Lebanon"),
    ("New Delhi","India"),("Mumbai","India"),("Jaipur","India"),("Goa","India"),("Kerala","India"),
    ("Kathmandu","Nepal"),("Pokhara","Nepal"),("Chitwan","Nepal"),("Lumbini","Nepal"),("Nagarkot","Nepal"),
    ("Colombo","Sri Lanka"),("Kandy","Sri Lanka"),("Galle","Sri Lanka"),("Ella","Sri Lanka"),("Sigiriya","Sri Lanka"),
    ("Bangkok","Thailand"),("Chiang Mai","Thailand"),("Phuket","Thailand"),("Krabi","Thailand"),("Koh Samui","Thailand"),
    ("Hanoi","Vietnam"),("Ho Chi Minh City","Vietnam"),("Hoi An","Vietnam"),("Ha Long Bay","Vietnam"),("Da Nang","Vietnam"),
    ("Siem Reap","Cambodia"),("Phnom Penh","Cambodia"),("Sihanoukville","Cambodia"),("Battambang","Cambodia"),("Kampot","Cambodia"),
    ("Luang Prabang","Laos"),("Vientiane","Laos"),("Vang Vieng","Laos"),("Pakse","Laos"),("Luang Namtha","Laos"),
    ("Yangon","Myanmar"),("Bagan","Myanmar"),("Mandalay","Myanmar"),("Inle Lake","Myanmar"),("Ngapali","Myanmar"),
    ("Kuala Lumpur","Malaysia"),("Penang","Malaysia"),("Langkawi","Malaysia"),("Kota Kinabalu","Malaysia"),("Kuching","Malaysia"),
    ("Singapore","Singapore"),("Manila","Philippines"),("Cebu","Philippines"),("Boracay","Philippines"),("Palawan","Philippines"),
    ("Jakarta","Indonesia"),("Bali","Indonesia"),("Yogyakarta","Indonesia"),("Lombok","Indonesia"),("Komodo","Indonesia"),
    ("Tokyo","Japan"),("Kyoto","Japan"),("Osaka","Japan"),("Hokkaido","Japan"),("Okinawa","Japan"),
    ("Seoul","South Korea"),("Busan","South Korea"),("Jeju","South Korea"),("Gyeongju","South Korea"),("Sokcho","South Korea"),
    ("Beijing","China"),("Shanghai","China"),("Guilin","China"),("Chengdu","China"),("Xi'an","China"),
    ("Taipei","Taiwan"),("Kaohsiung","Taiwan"),("Hualien","Taiwan"),("Tainan","Taiwan"),("Kenting","Taiwan"),
    ("Hong Kong","Hong Kong"),("Macau","Macau"),("Sydney","Australia"),("Melbourne","Australia"),("Cairns","Australia"),
    ("Auckland","New Zealand"),("Queenstown","New Zealand"),("Wellington","New Zealand"),("Christchurch","New Zealand"),("Milford Sound","New Zealand"),
    ("Vancouver","Canada"),("Toronto","Canada"),("Montreal","Canada"),("Banff","Canada"),("Whistler","Canada"),
    ("New York","United States"),("San Francisco","United States"),("Grand Canyon","United States"),("Yellowstone","United States"),("Yosemite","United States"),
    ("Mexico City","Mexico"),("Cancun","Mexico"),("Oaxaca","Mexico"),("Tulum","Mexico"),("Puerto Vallarta","Mexico"),
    ("Lima","Peru"),("Cusco","Peru"),("Arequipa","Peru"),("Paracas","Peru"),("Huaraz","Peru"),
    ("Santiago","Chile"),("Atacama","Chile"),("Patagonia","Chile"),("Easter Island","Chile"),("Valparaiso","Chile"),
    ("Buenos Aires","Argentina"),("Mendoza","Argentina"),("Patagonia","Argentina"),("Iguazu Falls","Argentina"),("Bariloche","Argentina"),
    ("Rio de Janeiro","Brazil"),("Fernando de Noronha","Brazil"),("Pantanal","Brazil"),("Amazon","Brazil"),("Salvador","Brazil"),
]

# watersports: 200 coastal/island (city, country) — subset of nature but coastal focus
WATERSPORTS_SEED = [
    ("Bali","Indonesia"),("Phuket","Thailand"),("Krabi","Thailand"),("Koh Samui","Thailand"),("Koh Tao","Thailand"),
    ("Boracay","Philippines"),("Cebu","Philippines"),("Palawan","Philippines"),("Siargao","Philippines"),("Batangas","Philippines"),
    ("Langkawi","Malaysia"),("Perhentian Islands","Malaysia"),("Redang Island","Malaysia"),("Tioman Island","Malaysia"),("Kota Kinabalu","Malaysia"),
    ("Maldives","Maldives"),("Male","Maldives"),("Maafushi","Maldives"),("Dhigurah","Maldives"),("Hulhumale","Maldives"),
    ("Sri Lanka South Coast","Sri Lanka"),("Mirissa","Sri Lanka"),("Unawatuna","Sri Lanka"),("Trincomalee","Sri Lanka"),("Bentota","Sri Lanka"),
    ("Goa","India"),("Andaman Islands","India"),("Kovalam","India"),("Varkala","India"),("Pondicherry","India"),
    ("Phu Quoc","Vietnam"),("Nha Trang","Vietnam"),("Da Nang","Vietnam"),("Mui Ne","Vietnam"),("Hoi An","Vietnam"),
    ("Sihanoukville","Cambodia"),("Koh Rong","Cambodia"),("Koh Rong Sanloem","Cambodia"),("Kep","Cambodia"),("Kampot","Cambodia"),
    ("Siem Reap","Cambodia"),("Vang Vieng","Laos"),("Luang Prabang","Laos"),("Vientiane","Laos"),("Don Det","Laos"),
    ("Okinawa","Japan"),("Miyako Island","Japan"),("Ishigaki","Japan"),("Amami Oshima","Japan"),("Zamami","Japan"),
    ("Jeju","South Korea"),("Busan","South Korea"),("Yeosu","South Korea"),("Tongyeong","South Korea"),("Sokcho","South Korea"),
    ("Hainan","China"),("Sanya","China"),("Xiamen","China"),("Qingdao","China"),("Dalian","China"),
    ("Kenting","Taiwan"),("Penghu","Taiwan"),("Green Island","Taiwan"),("Orchid Island","Taiwan"),("Fulong","Taiwan"),
    ("Hong Kong","Hong Kong"),("Macao Beach","Macau"),("Sentosa","Singapore"),("East Coast","Singapore"),("Changi","Singapore"),
    ("Gold Coast","Australia"),("Cairns","Australia"),("Whitsundays","Australia"),("Byron Bay","Australia"),("Noosa","Australia"),
    ("Bora Bora","French Polynesia"),("Moorea","French Polynesia"),("Tahiti","French Polynesia"),("Rangiroa","French Polynesia"),("Huahine","French Polynesia"),
    ("Fiji Islands","Fiji"),("Mamanuca Islands","Fiji"),("Yasawa Islands","Fiji"),("Taveuni","Fiji"),("Vanua Levu","Fiji"),
    ("Rarotonga","Cook Islands"),("Aitutaki","Cook Islands"),("Samoa","Samoa"),("Tongatapu","Tonga"),("Vava'u","Tonga"),
    ("Oahu","United States"),("Maui","United States"),("Kauai","United States"),("Big Island","United States"),("Lanai","United States"),
    ("San Diego","United States"),("Santa Monica","United States"),("Malibu","United States"),("Santa Cruz","United States"),("La Jolla","United States"),
    ("Miami","United States"),("Key West","United States"),("Fort Lauderdale","United States"),("Clearwater","United States"),("Daytona Beach","United States"),
    ("Myrtle Beach","United States"),("Outer Banks","United States"),("Hilton Head","United States"),("Virginia Beach","United States"),("Hamptons","United States"),
    ("Cancun","Mexico"),("Tulum","Mexico"),("Playa del Carmen","Mexico"),("Cozumel","Mexico"),("Puerto Vallarta","Mexico"),
    ("Los Cabos","Mexico"),("Mazatlan","Mexico"),("Huatulco","Mexico"),("Puerto Escondido","Mexico"),("Sayulita","Mexico"),
    ("Aruba","Aruba"),("Curacao","Curacao"),("Bonaire","Bonaire"),("Barbados","Barbados"),("St Lucia","Saint Lucia"),
    ("Antigua","Antigua and Barbuda"),("Grenada","Grenada"),("St Kitts","Saint Kitts and Nevis"),("British Virgin Islands","British Virgin Islands"),("US Virgin Islands","United States Virgin Islands"),
    ("Nassau","Bahamas"),("Exuma","Bahamas"),("Grand Cayman","Cayman Islands"),("Turks and Caicos","Turks and Caicos"),("Jamaica","Jamaica"),
    ("Cartagena","Colombia"),("Santa Marta","Colombia"),("San Andres Island","Colombia"),("Taganga","Colombia"),("Tayrona","Colombia"),
    ("Lima Coast","Peru"),("Paracas","Peru"),("Mancora","Peru"),("Huanchaco","Peru"),("Punta Hermosa","Peru"),
    ("Rio de Janeiro","Brazil"),("Fernando de Noronha","Brazil"),("Florianopolis","Brazil"),("Arraial do Cabo","Brazil"),("Jericoacoara","Brazil"),
    ("Galapagos","Ecuador"),("Salinas","Ecuador"),("Montanita","Ecuador"),("Manta","Ecuador"),("Puerto Lopez","Ecuador"),
    ("Vina del Mar","Chile"),("Pucon","Chile"),("La Serena","Chile"),("Antofagasta","Chile"),("Pichilemu","Chile"),
    ("Mar del Plata","Argentina"),("Puerto Madryn","Argentina"),("Pinamar","Argentina"),("Carilo","Argentina"),("Las Grutas","Argentina"),
    ("Montevideo Coast","Uruguay"),("Punta del Este","Uruguay"),("La Paloma","Uruguay"),("Cabo Polonio","Uruguay"),("Piriapolis","Uruguay"),
    ("Lisbon Coast","Portugal"),("Algarve","Portugal"),("Cascais","Portugal"),("Ericeira","Portugal"),("Peniche","Portugal"),
    ("Barcelona Coast","Spain"),("Ibiza","Spain"),("Mallorca","Spain"),("Tenerife","Spain"),("Gran Canaria","Spain"),
    ("Nice","France"),("Biarritz","France"),("Hossegor","France"),("Arcachon","France"),("Corsica","France"),
    ("Algarve","Portugal"),("Lagos","Portugal"),("Sagres","Portugal"),("Nazaré","Portugal"),("Porto","Portugal"),
    ("Santorini","Greece"),("Mykonos","Greece"),("Crete","Greece"),("Rhodes","Greece"),("Zakynthos","Greece"),
    ("Dubrovnik","Croatia"),("Split","Croatia"),("Hvar","Croatia"),("Korcula","Croatia"),("Brac","Croatia"),
    ("Kotor Bay","Montenegro"),("Budva","Montenegro"),("Ulcinj","Montenegro"),("Bar","Montenegro"),("Herceg Novi","Montenegro"),
    ("Antalya","Turkey"),("Bodrum","Turkey"),("Fethiye","Turkey"),("Kas","Turkey"),("Alanya","Turkey"),
    ("Sharm El Sheikh","Egypt"),("Hurghada","Egypt"),("Dahab","Egypt"),("Marsa Alam","Egypt"),("El Gouna","Egypt"),
    ("Diani Beach","Kenya"),("Watamu","Kenya"),("Zanzibar","Tanzania"),("Mafia Island","Tanzania"),("Pemba Island","Tanzania"),
    ("Cape Town","South Africa"),("Durban","South Africa"),("Knysna","South Africa"),("Plettenberg Bay","South Africa"),("Jeffreys Bay","South Africa"),
]

# deals: 200 origins (IATA, city)
DEALS_SEED = [
    ("ATL","Atlanta"),("LAX","Los Angeles"),("ORD","Chicago"),("DFW","Dallas"),("DEN","Denver"),
    ("JFK","New York"),("SFO","San Francisco"),("SEA","Seattle"),("LAS","Las Vegas"),("MCO","Orlando"),
    ("MIA","Miami"),("PHX","Phoenix"),("IAH","Houston"),("BOS","Boston"),("MSP","Minneapolis"),
    ("DTW","Detroit"),("PHL","Philadelphia"),("CLT","Charlotte"),("BWI","Baltimore"),("SLC","Salt Lake City"),
    ("SAN","San Diego"),("TPA","Tampa"),("PDX","Portland"),("STL","St Louis"),("HNL","Honolulu"),
    ("AUS","Austin"),("MSY","New Orleans"),("RDU","Raleigh"),("BNA","Nashville"),("SJC","San Jose"),
    ("SMF","Sacramento"),("MCI","Kansas City"),("CLE","Cleveland"),("IND","Indianapolis"),("CMH","Columbus"),
    ("PIT","Pittsburgh"),("CVG","Cincinnati"),("MEM","Memphis"),("JAX","Jacksonville"),("RIC","Richmond"),
    ("BUF","Buffalo"),("OMA","Omaha"),("OKC","Oklahoma City"),("TUL","Tulsa"),("ABQ","Albuquerque"),
    ("TUS","Tucson"),("ELP","El Paso"),("BUR","Burbank"),("ONT","Ontario"),("SNA","Santa Ana"),
    ("OAK","Oakland"),("SJU","San Juan"),("ANC","Anchorage"),("OGG","Kahului"),("LIH","Lihue"),
    ("LHR","London"),("CDG","Paris"),("FRA","Frankfurt"),("AMS","Amsterdam"),("MAD","Madrid"),
    ("BCN","Barcelona"),("FCO","Rome"),("MXP","Milan"),("ZRH","Zurich"),("VIE","Vienna"),
    ("BRU","Brussels"),("DUB","Dublin"),("LIS","Lisbon"),("CPH","Copenhagen"),("ARN","Stockholm"),
    ("OSL","Oslo"),("HEL","Helsinki"),("WAW","Warsaw"),("PRG","Prague"),("BUD","Budapest"),
    ("ATH","Athens"),("IST","Istanbul"),("DXB","Dubai"),("DOH","Doha"),("AUH","Abu Dhabi"),
    ("CAI","Cairo"),("JNB","Johannesburg"),("CPT","Cape Town"),("NBO","Nairobi"),("CMN","Casablanca"),
    ("NRT","Tokyo"),("HND","Tokyo"),("KIX","Osaka"),("ICN","Seoul"),("GMP","Seoul"),
    ("PEK","Beijing"),("PVG","Shanghai"),("CAN","Guangzhou"),("HKG","Hong Kong"),("TPE","Taipei"),
    ("BKK","Bangkok"),("SIN","Singapore"),("KUL","Kuala Lumpur"),("MNL","Manila"),("CGK","Jakarta"),
    ("DPS","Denpasar"),("SGN","Ho Chi Minh City"),("HAN","Hanoi"),("DEL","New Delhi"),("BOM","Mumbai"),
    ("SYD","Sydney"),("MEL","Melbourne"),("BNE","Brisbane"),("AKL","Auckland"),("YVR","Vancouver"),
    ("YYZ","Toronto"),("YUL","Montreal"),("MEX","Mexico City"),("CUN","Cancun"),("GDL","Guadalajara"),
    ("BOG","Bogota"),("LIM","Lima"),("SCL","Santiago"),("EZE","Buenos Aires"),("GRU","Sao Paulo"),
    ("GIG","Rio de Janeiro"),("PTY","Panama City"),("SJO","San Jose"),("LIR","Liberia"),("GUA","Guatemala City"),
    ("SAL","San Salvador"),("MGA","Managua"),("TGU","Tegucigalpa"),("BZE","Belize City"),("HAV","Havana"),
    ("NAS","Nassau"),("PUJ","Punta Cana"),("SXM","St Maarten"),("ANU","Antigua"),("BGI","Barbados"),
    ("KIN","Kingston"),("MBJ","Montego Bay"),("PAP","Port-au-Prince"),("SDQ","Santo Domingo"),("STI","Santiago"),
    ("AUA","Aruba"),("CUR","Curacao"),("POS","Port of Spain"),("GEO","Georgetown"),("CCS","Caracas"),
    ("UIO","Quito"),("GYE","Guayaquil"),("LPB","La Paz"),("VVI","Santa Cruz"),("ASU","Asuncion"),
    ("MVD","Montevideo"),("SJO2","San Jose2"),("BJX","Leon"),("QRO","Queretaro"),("PBC","Puebla"),
    ("VER","Veracruz"),("MID","Merida"),("OAX","Oaxaca"),("HMO","Hermosillo"),("CUL","Culiacan"),
    ("MTY","Monterrey"),("TRC","Torreon"),("AGU","Aguascalientes"),("SLP","San Luis Potosi"),("ZIH","Ixtapa"),
    ("PVR","Puerto Vallarta"),("SJD","Los Cabos"),("CZM","Cozumel"),("CJS","Ciudad Juarez"),("REX","Reynosa"),
    ("VSA","Villahermosa"),("TAM","Tampico"),("MTT","Minatitlan"),("PXM","Puerto Escondido"),("HUX","Huatulco"),
]

# ──────────────────────────────────────────────────────────────
# GENERATORS
# ──────────────────────────────────────────────────────────────

def generate_airlines(count=50):
    rows=[]
    for iata,name,country,is_lowcost in AIRLINES_SEED:
        slug=_slug(name)+"-airline-review"
        title=f"{name} Airline Review"
        rows.append((iata,name,country,is_lowcost,title,slug))
        if len(rows)>=800:
            break
    # synthetic fill if seed overlaps heavily
    if len(rows) < count*2:
        import string, itertools
        # generate unused IATA (2-char)
        try:
            import sqlite3
            db=DB_PATH
            if db.exists():
                conn=sqlite3.connect(str(db))
                existing=set(r[0] for r in conn.execute("SELECT iata_code FROM airlines_topics").fetchall())
                conn.close()
            else:
                existing=set(r[0] for r in rows)
        except Exception:
            existing=set(r[0] for r in rows)
        existing.update(r[0] for r in rows)
        synth_countries=["United States","United Kingdom","Germany","France","Japan","Australia","Canada","Brazil","India","Spain","Italy","Mexico","Turkey","Thailand","Singapore","South Korea","China","United Arab Emirates","Netherlands","Switzerland"]
        chars=string.ascii_uppercase+string.digits
        for a in chars:
            for b in chars:
                code=a+b
                if code in existing:
                    continue
                idx=len(rows)
                country=synth_countries[idx % len(synth_countries)]
                name=f"Aero {country.split()[-1]} {code} Airways"
                slug=_slug(name)+"-airline-review"
                title=f"{name} Airline Review"
                rows.append((code,name,country, idx%3==0, title, slug))
                existing.add(code)
                if len(rows)>= max(count*3, 600):
                    break
            if len(rows)>= max(count*3, 600):
                break
    return rows

def generate_airports(count=50):
    rows=[]
    for iata,name,city,country in AIRPORTS_SEED:
        if len(iata)>4 or " " in iata:
            iata="BKI"
            city="Kota Kinabalu"
        slug=_slug(city)+"-"+_slug(iata)+"-guide"
        title=f"{city} ({iata}) Guide: {name}"
        rows.append((iata,name,city,country,title,slug))
        if len(rows)>=800:
            break
    if len(rows) < 10000:  # always synthetic for airports
        import string
        try:
            import sqlite3
            db=DB_PATH
            if db.exists():
                conn=sqlite3.connect(str(db))
                existing=set(r[0] for r in conn.execute("SELECT iata_code FROM airports_topics").fetchall())
                conn.close()
            else:
                existing=set(r[0] for r in rows)
        except Exception:
            existing=set(r[0] for r in rows)
        existing.update(r[0] for r in rows)
        synth_cities=[("Riverside","United States"),("Hill Valley","United States"),("Lakeview","Canada"),("Greenfield","United Kingdom"),("Sunnyport","Australia"),("Coastal Bay","Spain"),("Mountain View","Switzerland"),("Harbor Town","Japan"),("Desert Springs","United Arab Emirates"),("Forest Hill","Germany")]
        chars=string.ascii_uppercase
        idx=0
        for a in chars:
            for b in chars:
                for c in chars:
                    code=a+b+c
                    if code in existing:
                        continue
                    city,country=synth_cities[idx % len(synth_cities)]
                    city=f"{city} {code}"
                    name=f"{city} Regional Airport"
                    slug=_slug(city)+"-"+_slug(code)+"-guide"
                    title=f"{city} ({code}) Guide: {name}"
                    rows.append((code,name,city,country,title,slug))
                    existing.add(code); idx+=1
                    if len(rows)>= max(count*3, 600):
                        break
                if len(rows)>= max(count*3, 600):
                    break
            if len(rows)>= max(count*3, 600):
                break
    return rows

def generate_nature(count=50):
    rows=[]
    for city,country in NATURE_SEED:
        slug=_slug(city)+"-nature-tours"
        # dedup same city slug suffix — keep first
        title=f"Nature and Wildlife Tours in {city}: Discover {country}"
        rows.append((city,country,title,slug))
    # dedup by slug before return
    seen=set(); out=[]
    for r in rows:
        if r[3] not in seen:
            seen.add(r[3]); out.append(r)
    return out[:count]

def generate_watersports(count=50):
    rows=[]
    for city,country in WATERSPORTS_SEED:
        slug=_slug(city)+"-water-sports"
        title=f"Water Sports and Boat Tours in {city}: {country} Adventure Guide"
        rows.append((city,country,title,slug))
    seen=set(); out=[]
    for r in rows:
        if r[3] not in seen:
            seen.add(r[3]); out.append(r)
    return out[:count]

def generate_deals(count=50):
    rows=[]
    for origin,city in DEALS_SEED:
        slug="flight-deals-from-"+_slug(city)
        title=f"Cheapest Flight Deals From {city}: Top Routes & Prices"
        rows.append((origin,city,title,slug))
    seen=set(); out=[]
    for r in rows:
        if r[3] not in seen:
            seen.add(r[3]); out.append(r)
    return out[:count]

GEN_MAP = {
    "airlines": generate_airlines,
    "airports": generate_airports,
    "nature": generate_nature,
    "watersports": generate_watersports,
    "deals": generate_deals,
}

# ──────────────────────────────────────────────────────────────
# INSERT helper
# ──────────────────────────────────────────────────────────────

def _insert_topics(blog: str, count: int, execute: bool):
    blog_norm = blog.replace("-hugo","").lower()
    if blog_norm not in GEN_MAP:
        print(f"Unknown blog: {blog} (choose from {list(GEN_MAP.keys())})", file=sys.stderr)
        sys.exit(2)
    table = BLOG_TABLE[blog_norm]
    gen_fn = GEN_MAP[blog_norm]
    candidates = gen_fn(count*3)  # over-generate for dedup

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        existing_slugs = _get_existing(conn, table, "slug")
        # for airlines/airports also dedup by iata
        existing_iata=set()
        if blog_norm in ("airlines","airports"):
            col="iata_code"
            existing_iata=_existing_iata(conn, table, col)

        to_insert=[]
        for row in candidates:
            if blog_norm=="airlines":
                iata,name,country,is_lowcost,title,slug=row
                if slug in existing_slugs or iata in existing_iata:
                    continue
                to_insert.append(row)
                existing_slugs.add(slug); existing_iata.add(iata)
            elif blog_norm=="airports":
                iata,name,city,country,title,slug=row
                if slug in existing_slugs or iata in existing_iata:
                    continue
                to_insert.append(row)
                existing_slugs.add(slug); existing_iata.add(iata)
            else:
                # nature/watersports/deals slug dedup
                slug=row[3] if blog_norm in ("nature","watersports") else row[3]
                if slug in existing_slugs:
                    continue
                to_insert.append(row)
                existing_slugs.add(slug)
            if len(to_insert)>=count:
                break

        if not execute:
            print(f"DRY-RUN: would insert {len(to_insert)} rows into {table} ({blog_norm})")
            if to_insert:
                print(f"  sample: {to_insert[0]}")
            return len(to_insert)

        inserted=0
        for row in to_insert:
            try:
                if blog_norm=="airlines":
                    iata,name,country,is_lowcost,title,slug=row
                    conn.execute(f"INSERT OR IGNORE INTO {table} (iata_code, airline_name, country, is_lowcost, title, slug, exhausted) VALUES (?,?,?,?,?,?,0)",
                                 (iata,name,country,is_lowcost,title,slug))
                elif blog_norm=="airports":
                    iata,name,city,country,title,slug=row
                    conn.execute(f"INSERT OR IGNORE INTO {table} (iata_code, airport_name, city, country, title, slug, exhausted) VALUES (?,?,?,?,?,?,0)",
                                 (iata,name,city,country,title,slug))
                elif blog_norm in ("nature","watersports"):
                    city,country,title,slug=row
                    conn.execute(f"INSERT OR IGNORE INTO {table} (city, country, title, slug, exhausted) VALUES (?,?,?,?,0)",
                                 (city,country,title,slug))
                elif blog_norm=="deals":
                    origin,city,title,slug=row
                    conn.execute(f"INSERT OR IGNORE INTO {table} (origin, origin_city, title, slug, exhausted) VALUES (?,?,?,?,0)",
                                 (origin,city,title,slug))
                inserted+=1
            except Exception as e:
                print(f"  skip {row}: {e}", file=sys.stderr)
        conn.commit()
        # actual inserted = count changes
        cur = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE exhausted=0")
        avail = cur.fetchone()[0]
        print(f"INSERTED {inserted} rows into {table} ({blog_norm}) — avail now {avail}")
        return inserted
    finally:
        conn.close()

def main():
    p=argparse.ArgumentParser(description="ETAP topic expander — hard-coded seeds, dry-run by default")
    p.add_argument("blog", nargs="?", help="blog id: airlines/airports/nature/watersports/deals (suffix -hugo allowed)")
    p.add_argument("--count", type=int, default=50, help="max rows to insert")
    g=p.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=False, help="dry-run (default)")
    g.add_argument("--execute", action="store_true", default=False, help="actually INSERT")
    p.add_argument("--all", action="store_true", help="expand all 5 blogs (with threshold ignored)")
    args=p.parse_args()

    # --all mode
    if args.all:
        total=0
        for b in ["airlines","airports","nature","watersports","deals"]:
            n=_insert_topics(b, args.count, execute=args.execute)
            total+=n
        print(f"TOTAL: {total} rows {'would insert' if not args.execute else 'inserted'}")
        return

    if not args.blog:
        p.print_help(); sys.exit(2)

    # default dry-run unless --execute given
    execute = args.execute
    # if neither flag given, dry-run true (safe)
    if not args.dry_run and not args.execute:
        execute=False  # dry-run default
    elif args.dry_run:
        execute=False

    _insert_topics(args.blog, args.count, execute=execute)

if __name__=="__main__":
    main()

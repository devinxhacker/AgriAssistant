# Data Source Register

All knowledge sources are verified for public/open-access terms before ingestion. Only documents with `approval_status = approved` are retrievable by the assistant.

| Document | Source / Publisher | Crop | Region | Season | Publication Date | Version | Licence | Status |
|---|---|---|---|---|---|---|---|---|
| `icar_cotton_maharashtra.md` | ICAR-Central Institute for Cotton Research (CICR), Nagpur | Cotton | Maharashtra | Kharif | 2026-07-15 | 1.0 | Public Government Advisory (ICAR Open Access) | Approved |
| `icar_soybean_advisory.md` | ICAR-IISR Indore & VNMKV Parbhani | Soybean | Maharashtra | Kharif | 2026-06-20 | 1.0 | Public Government Advisory (ICAR Open Access) | Approved |
| `icar_wheat_rabi.md` | ICAR-IIWBR Karnal | Wheat | Uttar Pradesh | Rabi | 2026-10-10 | 1.0 | Public Government Advisory (ICAR Open Access) | Approved |
| `icar_rice_advisory.md` | ICAR-National Rice Research Institute (NRRI), Cuttack | Rice | All India | Kharif | 2026-07-05 | 1.0 | Public Government Advisory (ICAR Open Access) | Approved |
| `dogr_onion_maharashtra.md` | ICAR-Directorate of Onion and Garlic Research (DOGR), Rajgurunagar | Onion | Maharashtra | Rabi | 2026-09-12 | 1.0 | Public Government Advisory (ICAR Open Access) | Approved |
| `scheme_pmkisan.md` | Ministry of Agriculture & Farmers Welfare (PM-KISAN Portal) | All | All India | All | 2026-08-01 | 2.1 | Government Open Data / Public Circular | Approved |
| `scheme_pmfby.md` | Department of Agriculture & Farmers Welfare (PMFBY Guidelines) | All | All India | Kharif & Rabi | 2026-07-01 | 1.4 | Government Open Data / Public Circular | Approved |
| `scheme_kcc.md` | NABARD & Ministry of Agriculture (KCC Circular) | All | All India | All | 2026-06-15 | 1.2 | Government Open Data / Public Circular | Approved |

## Live Data Services (Never Indexed in Vector Store)

| Tool | Provider | Refresh / Cache TTL | Timestamp Policy |
|---|---|---|---|
| Mandi Prices | Agmarknet (`data.gov.in`) / e-NAM Snapshot | 30 minutes (`LIVE_CACHE_TTL_SECONDS=1800`) | Always includes `data_as_of` date |
| Weather & Agromet | Open-Meteo / IMD Agromet Snapshot | 30 minutes (`LIVE_CACHE_TTL_SECONDS=1800`) | Always includes `data_as_of` timestamp |

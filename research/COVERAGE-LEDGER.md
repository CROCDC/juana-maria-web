# Juana María — Search Coverage Ledger

**Purpose:** avoid re-covering ground. Any new research workflow MUST read this file first and
SKIP everything under "✅ COVERED". Pursue only "🟡 OPEN LEADS". Update at the end of every round.

- Round 1 (broad sweep, 10 agents) — DONE
- Round 2 (deep authenticated, 10 agents) — DONE
- Round 3 (IG API back online; sequential authenticated harvest) — DONE
- Local media after R1+R2+R3: **100 photos + 24 videos (~398 MB)** in `media/` (see SOURCES.md)

### Round 3 harvested (IG via owner's Chrome cookies + /tmp/dl_post.py)
- **@belenasad** BTS carousels `Cb0ZNlQOIMA`, `CfcOf7fu2A5`, `CYsDB9mAbd2`, `CWvaJg4lN73` → 31 stills ✓ (her feed has NO other JM posts)
- **@marcelobohemio** (owner) feed crawled (720 posts, 2021→2026); 9 explicitly-Juana-María posts → 17 photos + 10 videos ✓
  His OTHER boats are EXCLUDED: **Suri II**, **Firecrest**, Diego's **Teseo** (he names them separately; many Colonia posts are aboard *Suri II*).
- Note: IG web API (web_profile_info + /api/v1/media/{pk}/info/ with Chrome cookies + X-IG-App-ID) WORKS again; gallery-dl's IG extractor still broken — use `/tmp/dl_post.py <shortcode> <dir>` and `/tmp/ig.py user <name> <pages> <partial> > <out>`.

---

## ✅ COVERED — do NOT re-visit

### Harvested (downloaded; integrated into media/)
- **Finara CDN** photos `BALLENERA-CAMPOS-JUANA-MARIA-barco-velero-1..10.jpg` — 9 unique (−6 = dup of −5).
  CDN fully exhausted: −11..−20 and −scaled all 404. No more images there.
- **@finara_yachts** posts: carousel `CklPEqzr9Zs` (5 photos + 3 videos), reels `DF5UxYmufUv` (720p),
  `DKzWkyRO0fy` (480p, byte-identical re-post). All harvested.
- **FB** "Teseo Doble Proa" (`dobleproateseo`): aerial `885055293436634` (HQ 58MB) ✓ ; vycmadera group
  post `7712976545408914` photo (volviendo de Colonia) ✓.
- **FB** Marcelo Blanco: `fbwatch 1932826910492565` (low-angle sail) ✓ ; reels `3632743870360783`,
  `1113026550877403` ✓.
- **FB** North Sailing Gear video `451649683645921` ✓ ; **FB** Luis Valle `1576985902513219` (2014, oldest) ✓.
- **Los Pericos**: YT "La Distancia" `f_ZN-yupAVg` ✓ ; Vimeo "El Próximo Viernes" `644130051` (Belén Asad) ✓ ;
  FB making-of `1281258812512809` ✓ ; 13 BTS frames + hull-lettering/two-balleneras stills ✓.

### Fully crawled / enumerated → NOTHING (more) to get
- **@mgnautica** (282 posts, fully crawled) — NO Juana María by name (sold; listing was on MercadoLibre).
  Other balleneras present are different boats (Antártida 1949, Cisne, Bosch 1952). 
- **@mgnautica.udi** — Brazilian namesake, unrelated. EXCLUDE.
- **MG Náutica YouTube** (channel, ~60–93 vids) — no Juana María video.
- **MercadoLibre eshop** `/pagina/mgnautica` — JM absent (SOLD); only sister Antártida 1949 left.
- **Diego Blanco Flickr** (`diegojoseblanco`, 63–126 photos) — all the **sister Teseo**, not JM. EXCLUDE.
- **AAVC registry** (`/flota-argentina`, 85 boats) + **SCBA 2025/2026** + **33 Orientales 2026** entry lists/results
  — Juana María NOT entered anywhere (she's a cruiser, not a racer). Teseo & Pinta are the Campos entries.
- **Teseo Doble Proa YT channel** (38 vids) & **Diego Blanco YT** (8 vids) — Teseo only, no JM. EXCLUDE.
- **Belén Asad** YouTube (1 reel) & **Vimeo** (120 vids) — only `644130051` is JM-related (harvested).
- **Finara** Wayback (8 snapshots across 2 URL paths) — full text recovered; same 9 images; no extras.

### Checked but WALLED today (retry only from a logged-in browser; see OPEN)
- MercadoLibre `MLA-1974736222` / `-1458244415` / `-1509654865` (anti-bot even with Chrome cookies)
- Instagram individual `/p/` & `/reel/` & profiles via gallery-dl → **IG API broke mid-run** (gallery-dl & yt-dlp
  both failing on IG now); web_profile_info returns only newest 12. Deep IG pagination blocked by rate-limit.
- TikTok @finara.yachts / @mgnautica (JS challenge blocked enumeration)
- Club IG @cvsi_oficial / @yachtclubsanisidro / @aavelerosclasicos (rate-limited)

### Context-only (mined for facts; don't re-mine)
- ADAN (Campos bio; Los cisnes de la Isla) · Cadenazzi yard (lacolectivadeldelta, Wikipedia ARA Petrel, cibernautica)
- Juez Tedín (carlospaezdelatorre, Wikipedia) · REY = Registro Especial de Yates (Prefectura)
- Press: lanacion nid04042022, infobae David English (NOT the boat), rockar

### Dead ends / disambiguation (NEVER search again)
- Flickr / Pinterest / Wikimedia for the boat — keyword noise (whales, "Island of the Blue Dolphins")
- **Sister/other boats — NOT Juana María:** Teseo (Colin Archer doble-proa, Diego Blanco), Antártida (1949),
  Cisne (1952 Longobucco), Cimarrón, the 1950 Finara ballenera, Noy, Toba, Pinta, Huaglen, Simbad, "Suri II"
- Puerto Pirámides whale-watching boats · "Island of the Blue Dolphins" Juana María · whaling stations

---

## 🟡 OPEN LEADS — pursue next (NOT yet exhausted)

> All of these need a logged-in **browser** session (Chrome MCP / manual), because the IG/FB APIs broke for
> gallery-dl/yt-dlp this round. Best done by the owner in their browser, or via Chrome-DevTools MCP.

1. **@finara_yachts** deep feed (3759 posts) — crawl IN PROGRESS (R3); most JM content already harvested (reels + carousel).
2. **Marcelo Blanco FB Reels** (~50) & **North Sailing Gear FB Reels** (~60) — per-reel visual verify for JM (yt-dlp+chrome works for FB).
3. **MercadoLibre `MLA-1974736222` original photos** — via a real logged-in ML window, or directly from MG Náutica.
4. **TikTok** @finara.yachts (very likely mirrors the JM reels) & @mgnautica — retry challenge.
5. **Club IG albums:** @cvsi_oficial, @yachtclubsanisidro — classic-fleet regatta photos that may show JM at berth.
6. **REY matrícula / full bow inscription / owner chain** — Prefectura REY lookup or a clean hull/plaque close-up
   (the owner can just photograph the bronze plaque).

### Candidates for a future round 3
- Drone/photographer credits (Maiko Astariz drone, Camila Pozner DoP) → their portfolios may hold JM stills
- Dolores Barreiro (@dolibar) feed for candid on-deck shots from the 2021–22 shoots
- Wolf Credo (@wolfcredoproductionsco, 60 posts) BTS stills
- Local San Isidro / club print bulletins; AAVC census / classic-yacht books naming Campos balleneras

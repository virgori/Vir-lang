# Chrono — Architecture Design
## `stdlib/vir/chrono/`

> **Version:** 1.0
> **Spec target:** Vir v2.0
> **Date:** 2026-09-17
> **Prompt:** [`PROMPT.md`](PROMPT.md)

---

## 1. Tổng quan

`chrono` là subsystem Date/Time/Timezone/Astronomy của Vir standard library.
Được thiết kế theo tiêu chuẩn production-quality — đủ nghiêm túc để dùng trong
backend, hệ thống phân tán, scientific computing, astronomical engine và calendar
engine lâu dài.

Subsystem tách thành **5 layer độc lập**, từ tầng thấp lên cao:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 5 · Astronomy High-Level                             │
│  sun · planet · moon · term · seasons                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 4 · Astronomical Primitives                          │
│  astro/time · julian · angle · coordinates · sidereal       │
│  precession · nutation · aberration · refraction · event    │
│  vsop/ (evaluator + 8 planet tables)                        │
├─────────────────────────────────────────────────────────────┤
│  Layer 3 · Timezone                                         │
│  zone · transition · database · zoned                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 2 · Civil Date & Time                                │
│  date · timeofday · datetime · parse · format · calendar    │
├─────────────────────────────────────────────────────────────┤
│  Layer 1 · Core Time                                        │
│  instant · duration · clock                                 │
├─────────────────────────────────────────────────────────────┤
│  Foundation · Vir Runtime                                   │
│  rt/syscall · rt/intrinsics · core/result · core/option     │
└─────────────────────────────────────────────────────────────┘
```

**Nguyên tắc cốt lõi:**

- Layer thấp hơn **không được** import layer cao hơn
- Astronomy **không được** phụ thuộc vào timezone hay locale
- VSOP87D là backend của `sun`/`planet`, không lộ ra API cao nhất
- Mỗi module có Single Responsibility
- Không có global mutable state ngoài timezone cache (single-init)

---

## 2. Cây thư mục

```
stdlib/vir/chrono/
│
│   PROMPT.md               — Prompt gốc (yêu cầu thiết kế)
│   ARCHITECTURE.md         — Tài liệu này
│
├── time/
│   ├── instant.vri         — Instant: thời điểm tuyệt đối (i64 nanos Unix)
│   ├── duration.vri        — Duration: khoảng thời gian (i64 nanos, signed)
│   └── clock.vri           — Clock: wall / monotonic / highRes
│
├── date/
│   ├── date.vri            — Date: ngày dân sự (proleptic Gregorian)
│   ├── timeofday.vri       — TimeOfDay: giờ trong ngày (h/m/s/nano)
│   ├── datetime.vri        — DateTime: naive date+time (không timezone)
│   ├── parse.vri           — Parser: ISO 8601, RFC 3339, custom pattern
│   ├── format.vri          — Formatter: pattern-based output
│   └── calendar.vri        — Calendar utilities: leap, isoWeek, quarter...
│
├── timezone/
│   ├── zone.vri            — Zone: IANA timezone descriptor
│   ├── transition.vri      — Transition: TZif entry, binary search
│   ├── database.vri        — TZif loader: runtime IANA tzdb
│   └── zoned.vri           — ZonedDateTime: datetime + zone + offset
│
├── astro/
│   ├── time.vri            — AstroTime: UTC/TAI/TT/UT1/TDB + leap seconds
│   ├── julian.vri          — JulianDate: JD / MJD / J2000 / centuries
│   ├── angle.vri           — Angle: deg/rad/hour, normalization
│   ├── site.vri            — Site: observer lat/lon/elevation
│   ├── coordinates.vri     — Coordinate systems + transforms
│   ├── sidereal.vri        — GMST / GAST / Local Sidereal Time
│   ├── precession.vri      — IAU 2006 precession between epochs
│   ├── nutation.vri        — IAU 1980 nutation (106 terms)
│   ├── aberration.vri      — Annual aberration correction
│   ├── refraction.vri      — Atmospheric refraction
│   ├── event.vri           — Root finding: bisect / secant / newton
│   ├── sun.vri             — Sun: position + rise/set/twilight
│   ├── planet.vri          — Planets: heliocentric/geocentric/equatorial
│   ├── moon.vri            — Moon: Meeus Ch47, phase events
│   ├── term.vri            — 24 Solar Terms (tiet khi)
│   ├── seasons.vri         — Equinox / Solstice events
│   │
│   └── vsop/
│       ├── types.vri       — VsopTerm / VsopSeries / VsopVariable / VsopPlanetData
│       ├── evaluator.vri   — Sum A*cos(B+C*t) evaluator
│       ├── mercury.vri     — Mercury L/B/R full tables
│       ├── venus.vri       — Venus L/B/R full tables
│       ├── earth.vri       — Earth L/B/R full tables
│       ├── mars.vri        — Mars L/B/R full tables
│       ├── jupiter.vri     — Jupiter L/B/R full tables
│       ├── saturn.vri      — Saturn L/B/R full tables
│       ├── uranus.vri      — Uranus L/B/R full tables
│       └── neptune.vri     — Neptune L/B/R full tables
│
└── tests/
    ├── time_test.vri
    ├── date_test.vri
    ├── timezone_test.vri
    ├── julian_test.vri
    ├── vsop_test.vri
    └── astro_test.vri
```

---

## 3. Dependency Graph

```
clock ──────────────────────────────────────► rt/syscall
instant ────────────────────────────────────► rt/syscall
duration ───────────────────────────────────► (core types only)

date ───────────────────────────────────────► instant · duration
timeofday ──────────────────────────────────► (core types only)
datetime ───────────────────────────────────► date · timeofday · instant
parse ──────────────────────────────────────► datetime · date · timeofday
format ─────────────────────────────────────► datetime · date · timeofday
calendar ───────────────────────────────────► date

zone ───────────────────────────────────────► transition · instant
transition ─────────────────────────────────► (core types only)
database ───────────────────────────────────► zone · transition · rt/syscall
zoned ──────────────────────────────────────► datetime · zone · instant · database

astro/time ─────────────────────────────────► instant · duration
astro/julian ───────────────────────────────► astro/time · datetime
astro/angle ────────────────────────────────► math/basic
astro/site ─────────────────────────────────► astro/angle
astro/coordinates ──────────────────────────► astro/angle
astro/sidereal ─────────────────────────────► astro/angle · astro/julian
astro/precession ───────────────────────────► astro/angle · astro/julian
astro/nutation ─────────────────────────────► astro/angle · astro/julian
astro/aberration ───────────────────────────► astro/angle · astro/coordinates
astro/refraction ───────────────────────────► astro/angle
astro/event ────────────────────────────────► (core/result)
vsop/types ─────────────────────────────────► (core types only)
vsop/evaluator ─────────────────────────────► vsop/types · astro/angle · math/basic
vsop/{planet}.vri ──────────────────────────► vsop/types
astro/sun ──────────────────────────────────► vsop/evaluator · vsop/earth · astro/* · astro/event
astro/planet ───────────────────────────────► vsop/evaluator · vsop/{planets} · astro/* · astro/event
astro/moon ─────────────────────────────────► astro/angle · astro/julian · astro/event
astro/term ─────────────────────────────────► astro/sun · astro/event · astro/julian
astro/seasons ──────────────────────────────► astro/sun · astro/event · astro/julian
```

**Luật không được vi phạm:**

| Cấm | Lý do |
|-----|-------|
| `date` import từ `timezone` | Date là naive — không có timezone |
| `astro/*` import từ `timezone` | Astronomy dùng AstroTime, không local time |
| `vsop/evaluator` import từ `sun/planet` | Evaluator là primitive, không biết context |
| Layer N bỏ qua import Layer N+2 | Vi phạm SRP và khả năng test độc lập |

---

## 4. Layer 1 — Core Time

### 4.1 Instant

Đại diện một thời điểm tuyệt đối trên timeline, không có timezone.

```
Entity Instant
  nanosUnix : i64
    Nanoseconds từ Unix epoch (1970-01-01T00:00:00Z)
    Signed  →  hỗ trợ timestamps trước 1970
    64-bit  →  hỗ trợ tới năm 2262, không có year-2038 bug
```

| Hàm | Mô tả |
|-----|-------|
| `instant.now()` | Wall clock hiện tại (UTC) |
| `instant.fromSec(s: i64)` | Từ Unix seconds |
| `instant.fromMs(ms: i64)` | Từ Unix milliseconds |
| `instant.fromUs(us: i64)` | Từ Unix microseconds |
| `instant.fromNs(ns: i64)` | Từ Unix nanoseconds |
| `.seconds()` | Lấy Unix seconds |
| `.milliseconds()` | Lấy Unix milliseconds |
| `.microseconds()` | Lấy Unix microseconds |
| `.nanoseconds()` | Lấy Unix nanoseconds |
| `elapsed(start)` | Thời gian trôi qua từ start đến now |
| `since(start, end)` | Khoảng cách giữa hai Instant |
| `addDuration(inst, dur)` | Instant + Duration → Instant |
| `subDuration(inst, dur)` | Instant − Duration → Instant |
| `diff(a, b)` | Instant − Instant → Duration |
| `before(a, b)` / `after(a, b)` | Comparison |

Nguồn dữ liệu: `sys_clock_gettime(CLOCK_REALTIME, tp)` — không dùng libc.

---

### 4.2 Duration

```
Entity Duration
  nanos : i64    (signed nanoseconds, phạm vi ±292 năm)
```

**Constructors:**
`duration.fromNs(n)` · `fromUs(n)` · `fromMs(n)` · `fromSec(n)` · `fromMin(n)` · `fromHour(n)` · `fromDay(n)` · `fromWeek(n)`

**Operations:**
`add` · `sub` · `neg` · `abs` · `sign` · `mulInt` · `divInt` · `addChecked` · `subChecked`

**Conversions:**
`.toNs()` · `.toUs()` · `.toMs()` · `.toSec()` · `.toMin()` · `.toHour()`

---

### 4.3 Clock

```
clock.now()        → Instant   (wall clock UTC — dùng cho timestamps)
clock.monotonic()  → Instant   (monotonic — dùng để đo elapsed time)
clock.resolution() → Duration  (độ phân giải nhỏ nhất)
```

Quy tắc: Không dùng `clock.now()` để benchmark. Chỉ dùng `clock.monotonic()`.

---

## 5. Layer 2 — Civil Date & Time

### 5.1 Date

```
Entity Date
  year  : i32   (-292277..292277)
  month : i8    (1..12)
  day   : i8    (1..31, validated per month)
```

**Year 0 policy (documented):** Year 0 tồn tại (= 1 BCE). Negative years = BCE.
- −1 = 2 BCE, 0 = 1 BCE, 1 = 1 CE

**Constructor:** `date.create(y, m, d)` → `Result(Date, DateError)`

**Month overflow policy (documented, không silent):**
- `Jan 31.addMonths(1)` = `Feb 28` (clamp ngày, không tràn sang Mar)
- `Feb 29.addYears(1)` = `Feb 28` (năm không nhuận tiếp theo)

**Properties:**
`.year` · `.month` · `.day` · `.weekday` · `.dayOfYear`
`.weekOfYear` · `.isoWeekYear` · `.quarter` · `.epochDays`

**Arithmetic:**
`addDays(n)` · `addWeeks(n)` · `addMonths(n)` · `addYears(n)`

---

### 5.2 TimeOfDay

```
Entity TimeOfDay
  hour : i32   (0..23)
  min  : i32   (0..59)
  sec  : i32   (0..59)
  nano : i32   (0..999_999_999)
```

**Leap second policy (documented):** Không hỗ trợ giây 60.
Input sec=60 bị reject (Result::Err).

Computed: `.millisecond` · `.microsecond` · `.nanosecond`

---

### 5.3 DateTime (Naive)

```
Entity DateTime
  date      : Date
  timeofday : TimeOfDay
```

Ba khái niệm PHẢI phân biệt rõ:
- `Instant`       = thời điểm tuyệt đối (UTC nanoseconds)
- `DateTime`      = biểu diễn dân sự naive (không timezone)
- `ZonedDateTime` = datetime + zone (gắn với timeline thực)

**Operations:**
`add(dur)` · `sub(dur)` · `diff(other)` · `startOfDay()` · `endOfDay()`
`startOfMonth()` · `endOfMonth()` · `startOfYear()` · `endOfYear()`
`toInstant(utcOffsetSeconds: i64)` → `Instant`

---

### 5.4 Parse

| Format | Ví dụ |
|--------|-------|
| ISO 8601 calendar | `2026-09-17T10:30:00+07:00` |
| ISO 8601 + Z | `2026-09-17T10:30:00.123456789Z` |
| ISO 8601 ordinal | `2026-260T10:30:00Z` |
| ISO 8601 week | `2026-W38-4T10:30:00Z` |
| RFC 3339 | `2026-09-17T10:30:00.000Z` |
| Unix timestamp | `parse.fromUnix(i64)` |
| Custom pattern | `parse.withPattern(s, "yyyy/MM/dd HH:mm")` |

Pattern tokens: `yyyy` `yy` `MM` `M` `dd` `d` `HH` `H` `mm` `ss` `SSS` `SSSSSS` `SSSSSSSSS` `'literal'` `Z`

Return: `Result(DateTime, ParseError)`

---

### 5.5 Format

```
format.iso(dt)                 → "2026-09-17T10:30:00"
format.isoWithMs(dt)           → "2026-09-17T10:30:00.123"
format.rfc3339(dt, offsetSec)  → "2026-09-17T10:30:00+07:00"
format.pattern(dt, pat)        → string (custom pattern)
format.date(d)                 → "2026-09-17"
format.time(t)                 → "10:30:00"
```

---

### 5.6 Calendar

```
calendar.isLeapYear(year)       → bool   (400/100/4 rule)
calendar.daysInMonth(year, m)   → i32    (leap-aware)
calendar.daysInYear(year)       → i32    (365 or 366)
calendar.isoWeek(date)          → {week: i32, year: i32}
calendar.quarter(date)          → i8     (1..4)
calendar.weekday(date)          → Weekday (Mon=1..Sun=7, ISO 8601)
```

---

## 6. Layer 3 — Timezone

### 6.1 Zone

```
Entity Zone
  name        : string           (IANA name: "Asia/Ho_Chi_Minh")
  transitions : TransitionTable
  posixTail   : string           (POSIX TZ string cho future DST)
```

```
enum AmbiguousPolicy   : earlier | later | reject
enum NonexistentPolicy : forward | backward | reject
```

| Tình huống | Khi nào |
|-----------|---------|
| Ambiguous | Clock quay lui (DST backward) → cùng local time xảy ra 2 lần |
| Nonexistent | Clock nhảy tới (DST forward) → local time không tồn tại |

```
zone.utc()               → Zone   (built-in, no I/O)
zone.fixed(offsetSec)    → Zone   (simple fixed offset, no DST)
zone.offsetAt(inst)      → i32    (seconds east of UTC tại instant đó)
zone.isDstAt(inst)       → bool
zone.abbrevAt(inst)      → string ("ICT", "EDT", "JST", ...)
```

---

### 6.2 Transition

```
Entity Transition
  utcWhen     : i64    (Unix seconds khi transition xảy ra)
  offsetAfter : i32    (seconds east of UTC sau transition)
  isDst       : bool
  abbrev      : string

findTransition(table, unixSec: i64) → Transition   (binary search)
```

---

### 6.3 Database

TZif binary parser (v1/v2/v3). Không embed tzdata vào binary.

```
tzdb.load(name: string)    → Result(Zone, TzError)
tzdb.utc()                 → Zone          (built-in, no I/O)
tzdb.local()               → Result(Zone, TzError)  (/etc/localtime hoặc $TZ)
tzdb.version()             → string        (đọc version file từ tzdb)
```

Search paths (theo thứ tự):
1. `$VIRON_TZ_PATH`
2. `/usr/share/zoneinfo`
3. `/usr/lib/zoneinfo`
4. `/usr/share/lib/zoneinfo`
5. `/etc/zoneinfo`

Cache: global dict — lazy init, read-safe sau khi đã init.

---

### 6.4 ZonedDateTime

```
Entity ZonedDateTime
  instant : Instant    (nguồn sự thật — thời điểm tuyệt đối)
  zone    : Zone
  offset  : i32        (cached: seconds east of UTC)
  isDst   : bool       (cached)
  abbrev  : string     (cached)
```

Local datetime được tính on-demand từ `instant + offset`.

```
zoned.fromInstant(inst, zone)                      → ZonedDateTime
zoned.from(dt, zone, ambig, nonexist)              → Result(ZonedDateTime, TzError)

.to(otherZone)                                     → ZonedDateTime
    # Cùng instant, zone mới  →  đổi timezone (cách đúng)

.reassign(otherZone, ambig, nonexist)              → Result(ZonedDateTime, TzError)
    # Cùng local clock, zone mới  →  gắn timezone khác vào local time

.localDate()        → Date
.localTime()        → TimeOfDay
.localDatetime()    → DateTime
.formatRfc3339()    → string
```

Sự khác biệt QUAN TRỌNG:
- `.to("Asia/Tokyo")` = "Cùng thời điểm đó ở Tokyo là mấy giờ?"
- `.reassign("Asia/Tokyo")` = "Tôi muốn diễn giải local clock này như đang ở Tokyo"

---

## 7. Layer 4 — Astronomical Primitives

### 7.1 AstroTime & Time Scales

| Scale | Ký hiệu | Mô tả |
|-------|---------|-------|
| Universal Coordinated Time | utc | Đồng hồ dân sự, có leap seconds |
| International Atomic Time | tai | UTC − leap seconds (liên tục) |
| Terrestrial Time | tt | TAI + 32.184s (geocentric dynamical) |
| Universal Time | ut1 | Dựa trên quay Trái Đất (DUT1 = UT1−UTC) |
| Barycentric Dynamical Time | tdb | Ephemeris time cho solar system |

```
Entity AstroTime
  jdInt  : i64      (phần nguyên Julian Date)
  jdFrac : float    (phần lẻ Julian Date, 0.0..1.0)
  scale  : TimeScale

enum TimeScale : utc | tai | tt | ut1 | tdb
```

Tại sao split jdInt+jdFrac:
JD hiện tại ≈ 2.461.000. Float (f64) tại giá trị này có precision chỉ ~0.3ms.
Split int+frac giữ precision xuống dưới microsecond.

Conversions (mỗi bước có công thức riêng, không dùng offset giả):
```
UTC → TAI  : cộng số leap seconds tại thời điểm đó (từ bảng static)
TAI → TT   : cộng đúng 32.184 giây
TT  → TDB  : cộng correction nhỏ (~1.7ms max) do quỹ đạo lệch tâm
UTC → UT1  : cộng DUT1 (phải cung cấp từ caller — IERS bulletin)
```

Leap second table: 28 entries 1972-01-01..2017-01-01, embedded static const.

---

### 7.2 Julian Date

```
const J2000_JD          = 2451545.0    # 2000-01-01 12:00:00 TT
const MJD_EPOCH         = 2400000.5    # Modified Julian Date epoch
const JULIAN_CENTURY    = 36524.25     # days
const JULIAN_MILLENNIUM = 365242.5     # days

julianDate.fromDatetime(dt, scale)   → JulianDate
julianDate.toDatetime(jd)            → DateTime
.modifiedJulianDate                  → float  (JD - 2400000.5)
.julianCentury                       → float  ((JD - J2000) / JULIAN_CENTURY)
.julianMillennium                    → float  ((JD - J2000) / JULIAN_MILLENNIUM)
```

---

### 7.3 Angle

```
Entity Angle
  radians : float   (canonical — lưu nội tại bằng radians)
```

Constructors: `fromDeg(d)` · `fromRad(r)` · `fromHour(h)` · `fromArcmin(m)` · `fromArcsec(s)`

Properties (computed): `.deg` · `.rad` · `.hour` · `.arcmin` · `.arcsec`

Normalization (không rải mod 360 khắp codebase):
- `.norm360()` → [0°, 360°)
- `.norm180()` → (−180°, 180°]
- `.norm24h()` → [0h, 24h)

Operations: `add(a, b)` · `sub(a, b)` · `neg(a)` · `mul(a, f)` · `div(a, f)`

---

### 7.4 Coordinate Systems

```
Entity Ecliptic      longitude, latitude (Angle), distance (float, AU)
Entity Equatorial    rightAscension, declination (Angle), distance (float, AU)
Entity Horizontal    azimuth, altitude (Angle)
Entity Heliocentric  longitude, latitude (Angle), radius (float, AU)
Entity Geocentric    longitude, latitude (Angle), distance (float, AU)
```

Transforms:
```
eclipticToEquatorial(ecl, obliquity)     → Equatorial
equatorialToEcliptic(eq, obliquity)      → Ecliptic
equatorialToHorizontal(eq, lst, site)    → Horizontal
horizontalToEquatorial(hor, lst, site)   → Equatorial
```

- `obliquity` = true obliquity từ `nutation.trueObliquity(jd)`
- `lst` = Local Sidereal Time từ `sidereal.localSidereal()`

---

### 7.5 Site (Observer)

```
Entity Site
  latitude  : Angle   (+ = Bắc bán cầu)
  longitude : Angle   (+ = Đông — east positive, chuẩn thiên văn)
  elevation : float   (meters above sea level)
```

Convention longitude **East positive** dùng nhất quán toàn codebase.

---

### 7.6 Sidereal Time

```
gmst(jd: float)                        → Angle  (Greenwich Mean Sidereal Time)
gast(jd, nutLon, obliquity)            → Angle  (Greenwich Apparent Sidereal Time)
localSidereal(gast, site)              → Angle  (Local Sidereal Time)
```

Công thức GMST: IAU 1982 polynomial (Meeus Eq. 12.4).

---

### 7.7 Precession

IAU 2006 (Capitaine et al. 2003):
```
precessEquatorial(ra, dec, fromJd, toJd)   → Equatorial
precessEcliptic(lon, lat, fromJd, toJd)    → Ecliptic
```

---

### 7.8 Nutation

IAU 1980 nutation series — **106 terms, đầy đủ, không truncate**:
```
nutation(jd: float)   → NutationResult
  .deltaPsi : Angle   (nutation in longitude)
  .deltaEps : Angle   (nutation in obliquity)

meanObliquity(jd)     → Angle   (IAU/Laskar 1986 polynomial)
trueObliquity(jd)     → Angle   (meanObliquity + deltaEps)
```

---

### 7.9 Aberration

```
annualAberration(equatorial, jd)   → Equatorial
```

Constant of aberration κ = 20.49552 arcseconds.
Chỉ áp dụng khi tính **apparent position** — không trộn với geometric.

---

### 7.10 Atmospheric Refraction

```
Entity Atmosphere
  pressure    : float   (Pa)
  temperature : float   (K)

atmosphere.standard()                  → Atmosphere  (101325 Pa, 288.15 K)
refraction(altitude: Angle, atm)       → Angle       (correction to add)
```

- altitude < −2°: returns angle 0 (không áp dụng khi quá xa dưới horizon)
- Có thể bỏ qua để lấy geometric position

---

### 7.11 Root Finding (Event Search)

```
bisect(f, a, b, tolerance, maxIter)        → Result(float, SolverError)
secant(f, x0, x1, tolerance, maxIter)     → Result(float, SolverError)
newton(f, df, x0, tolerance, maxIter)     → Result(float, SolverError)
bracket(f, start, step, target, maxSteps) → Result({a: float, b: float}, SolverError)

enum SolverError : noConvergence | noBracket | invalidInput | diverged
```

Tolerance unit: Julian days. Thường 1e-8 JD ≈ 0.86ms cho astronomical events.

---

## 8. Layer 5 — Astronomy High-Level

### 8.1 Sun

```
Entity SunPosition
  longitude               : Angle   (ecliptic geometric)
  latitude                : Angle   (ecliptic geometric, rất nhỏ)
  distance                : float   (AU)
  rightAscension          : Angle   (equatorial geometric)
  declination             : Angle   (equatorial geometric)
  apparentLongitude       : Angle   (+ nutation + aberration)
  apparentRightAscension  : Angle
  apparentDeclination     : Angle
```

Implementation pipeline:
```
AstroTime (UTC) → AstroTime (TDB) → Julian millennium t
  → VSOP87D Earth L/B/R (heliocentric)
  → Negate vector → Sun geocentric ecliptic
  → FK5 correction
  → Apply nutation → apparentLongitude
  → Apply aberration
  → eclipticToEquatorial (trueObliquity) → apparent equatorial
```

```
sun(time: AstroTime)                    → SunPosition
sun.rise(date: Date, site: Site)        → Option(AstroTime)
sun.set(date: Date, site: Site)         → Option(AstroTime)
sun.noon(date: Date, site: Site)        → AstroTime
sun.twilight(date, site, kind)          → {rise: Option(AstroTime), set: Option(AstroTime)}

enum TwilightKind : civil | nautical | astronomical
    # civil        = -6° below horizon
    # nautical     = -12°
    # astronomical = -18°
```

Polar day / polar night: trả None. Không fake timestamp.

---

### 8.2 Planets

```
enum Planet : mercury | venus | mars | jupiter | saturn | uranus | neptune

Entity PlanetPosition
  heliocentric      : Heliocentric  (VSOP87D output)
  geocentric        : Ecliptic      (Earth-centered)
  equatorial        : Equatorial    (after coordinate transform)
  distanceFromSun   : float         (AU)
  distanceFromEarth : float         (AU)

planet(p: Planet, time: AstroTime)        → PlanetPosition
planet.rise(p, date: Date, site: Site)    → Option(AstroTime)
planet.set(p, date: Date, site: Site)     → Option(AstroTime)
```

---

### 8.3 Moon

Moon dùng **Meeus Chapter 47** — không dùng VSOP87D.
VSOP87D là planetary theory; Moon cần lunar theory riêng.

```
Entity MoonPosition
  longitude      : Angle   (geocentric ecliptic)
  latitude       : Angle   (geocentric ecliptic)
  distance       : float   (km — Earth center to Moon center)
  rightAscension : Angle
  declination    : Angle
  phase          : Angle   (0=New, 90=FirstQ, 180=Full, 270=LastQ)
  illumination   : float   (0.0..1.0)
  age            : float   (days since last new moon)

moon(time: AstroTime)              → MoonPosition
moon.newMoon(nearJd: float)        → AstroTime
moon.fullMoon(nearJd: float)       → AstroTime
moon.firstQuarter(nearJd: float)   → AstroTime
moon.lastQuarter(nearJd: float)    → AstroTime
```

Phase events dùng bisection — không dùng ngày âm lịch.

---

### 8.4 Solar Terms (24 Tiet Khi)

24 tiết khí = Sun đạt 24 góc hoàng kinh liên tiếp, cách nhau 15°.
Theo truyền thống bắt đầu từ Tiểu Hàn (315°):

| Index | Hoàng kinh | Tên CN | Tên EN |
|-------|-----------|--------|--------|
| 0 | 315° | 小寒 | Minor Cold |
| 1 | 330° | 大寒 | Major Cold |
| 2 | 345° | 立春 | Start of Spring |
| 3 | 0° | 雨水 | Rain Water |
| 4 | 15° | 驚蟄 | Awakening of Insects |
| 5 | 30° | 春分 | Vernal Equinox |
| 6 | 45° | 清明 | Clear and Bright |
| 7 | 60° | 穀雨 | Grain Rain |
| 8 | 75° | 立夏 | Start of Summer |
| 9 | 90° | 小滿 | Grain Buds |
| 10 | 105° | 芒種 | Grain in Ear |
| 11 | 120° | 夏至 | Summer Solstice |
| 12 | 135° | 小暑 | Minor Heat |
| 13 | 150° | 大暑 | Major Heat |
| 14 | 165° | 立秋 | Start of Autumn |
| 15 | 180° | 處暑 | End of Heat |
| 16 | 195° | 白露 | White Dew |
| 17 | 210° | 秋分 | Autumnal Equinox |
| 18 | 225° | 寒露 | Cold Dew |
| 19 | 240° | 霜降 | Frost's Descent |
| 20 | 255° | 立冬 | Start of Winter |
| 21 | 270° | 小雪 | Minor Snow |
| 22 | 285° | 大雪 | Major Snow |
| 23 | 300° | 冬至 | Winter Solstice |

```
Entity SolarTerm
  index    : i32
  name     : string   (Chinese traditional: 小寒, 大寒, ...)
  nameEn   : string   (English: Minor Cold, Major Cold, ...)
  longitude: Angle    (target: 315°, 330°, ..., 300°)
  instant  : AstroTime

term.at(time: AstroTime)     → SolarTerm   (term chứa thời điểm này)
term.next(time: AstroTime)   → SolarTerm
term.prev(time: AstroTime)   → SolarTerm
term.forYear(year: i32)      → [SolarTerm]  (tất cả 24 terms trong năm)
```

Implementation: bisection trên `sun(t).apparentLongitude - target`.
Không hardcode theo timezone. Core result là AstroTime; local date tính ở layer zoned.

---

### 8.5 Equinox & Solstice

```
seasons.marchEquinox(year: i32)       → AstroTime   (apparentLongitude = 0°)
seasons.juneSolstice(year: i32)       → AstroTime   (apparentLongitude = 90°)
seasons.septemberEquinox(year: i32)   → AstroTime   (apparentLongitude = 180°)
seasons.decemberSolstice(year: i32)   → AstroTime   (apparentLongitude = 270°)
seasons.all(year: i32)                → SeasonBoundaries

entity SeasonBoundaries
  march     : AstroTime
  june      : AstroTime
  september : AstroTime
  december  : AstroTime
```

Tất cả là AstroTime. Timezone conversion làm ở layer zoned.

---

## 9. VSOP87D

### 9.1 Công thức tổng quát

```
Biến L, B, R của mỗi hành tinh:

L = L0 + L1*t + L2*t^2 + L3*t^3 + ...

Lk = sum_i  Ai * cos(Bi + Ci*t)

t = Julian millennia từ J2000.0 (TDB)
  = (JD_TDB - 2451545.0) / 365250.0
```

### 9.2 Data Model

```
Entity VsopTerm
  a : float   (Amplitude)
  b : float   (Phase, radians)
  c : float   (Frequency, rad/millennium)

Entity VsopSeries
  terms : [VsopTerm]     (tất cả terms cho một power level Lk)

Entity VsopVariable
  series : [VsopSeries]  (series cho L0, L1, L2, ...)

Entity VsopPlanetData
  l : VsopVariable   (longitude)
  b : VsopVariable   (latitude)
  r : VsopVariable   (radius, AU)
```

### 9.3 Evaluator

```
evalSeries(s: VsopSeries, t: float)     → float
    = sum_i  s.terms[i].a * cos(s.terms[i].b + s.terms[i].c * t)

evalVariable(v: VsopVariable, t: float) → float
    = sum_k  t^k * evalSeries(v.series[k], t)

evalPlanet(data, t: float)              → {longitude, latitude, radius}
    Output: radians, radians, AU

vsop.position(planet: Planet, time: AstroTime) → Heliocentric
    High-level: auto-converts time to t, returns Heliocentric entity
```

### 9.4 Planet Coverage

| Planet | L series | B series | R series | Approx terms |
|--------|---------|---------|---------|-------------|
| Mercury | L0..L5 | B0..B2 | R0..R4 | ~208 |
| Venus | L0..L5 | B0..B4 | R0..R4 | ~216 |
| Earth | L0..L5 | B0..B1 | R0..R4 | ~215 |
| Mars | L0..L5 | B0..B4 | R0..R4 | ~382 |
| Jupiter | L0..L5 | B0..B5 | R0..R5 | ~565 |
| Saturn | L0..L6 | B0..B6 | R0..R6 | ~998 |
| Uranus | L0..L5 | B0..B4 | R0..R4 | ~424 |
| Neptune | L0..L5 | B0..B4 | R0..R4 | ~350 |
| **Total** | | | | **~3358** |

Tất cả được embed dưới dạng `const` arrays — zero heap allocation, .rodata section.

### 9.5 Precision Range

VSOP87D cho kết quả tốt nhất trong **-2000..+6000** Julian years.
Ngoài phạm vi này error tăng. Được document rõ trong API.

---

## 10. Error Model

```
enum DateError
  invalidMonth(month: i32)
  invalidDay(year: i32, month: i32, day: i32)
  outOfRange(year: i32)

enum TimeError
  invalidHour(hour: i32)
  invalidMinute(min: i32)
  invalidSecond(sec: i32)
  invalidNano(nano: i32)

enum TzError
  zoneNotFound(name: string)
  ambiguous(name: string, datetime: DateTime)
  nonexistent(name: string, datetime: DateTime)
  databaseNotFound
  parseError(offset: i32)

enum ParseError
  unexpectedEnd(pos: i32)
  invalidChar(pos: i32, expected: string, got: string)
  invalidField(field: string, value: string)
  unsupportedFormat(hint: string)

enum SolverError
  noConvergence(iterations: i32)
  noBracket
  invalidInput(reason: string)
  diverged

enum AstroError
  outOfRange(what: string, value: float, min: float, max: float)
  invalidTimeScale(expected: TimeScale, got: TimeScale)
```

Không dùng sentinel values (-1, 9999, NaN) cho lỗi nghiệp vụ.

---

## 11. Memory Model

| Type | Semantics | Storage |
|------|-----------|---------|
| Instant | Copy | Stack (i64, 8 bytes) |
| Duration | Copy | Stack (i64, 8 bytes) |
| Date | Copy | Stack (i32+i8+i8, 6 bytes) |
| TimeOfDay | Copy | Stack (4×i32, 16 bytes) |
| DateTime | Copy | Stack (Date + TimeOfDay) |
| Angle | Copy | Stack (f64, 8 bytes) |
| AstroTime | Copy | Stack (i64+f64+enum, 24 bytes) |
| JulianDate | Copy | Stack (f64+enum) |
| Site | Copy | Stack (3 Angles + f64) |
| Ecliptic, Equatorial, Horizontal | Copy | Stack |
| SunPosition | Copy | Stack (8 Angles + 1 float) |
| PlanetPosition | Move | Stack (4 entities) |
| Zone | Move | Arena (string + TransitionTable) |
| ZonedDateTime | Move | Stack (Instant + Zone borrow + cached fields) |
| VSOP87D term arrays | Static | .rodata section (const) |
| tzdb cache | Global | Arena (single-write lazy init) |

VSOP87D hot path: không allocation. Loop qua static const arrays.

---

## 12. Naming Conventions

| Loại | Convention | Ví dụ |
|------|-----------|-------|
| Module | lowercase | `date`, `astro`, `vsop` |
| Entity | PascalCase | `Duration`, `ZonedDateTime`, `SunPosition` |
| Enum | PascalCase | `Planet`, `TimeScale`, `AmbiguousPolicy` |
| Enum variant | camelCase | `mercury`, `earlier`, `noConvergence` |
| Function | camelCase | `isLeapYear`, `fromEpochDays`, `localSidereal` |
| Const | ALL_CAPS | `J2000_JD`, `JULIAN_CENTURY`, `MJD_EPOCH` |
| Private helper | `_` prefix | `_findTransition`, `_evalTerm` |

Không dùng: `getX` · `setX` · `calculateX` · `computeX`
Không viết tắt astronomy: `rightAscension` không phải `ra`, `declination` không phải `dec`
Không `snake_case` trong public API.

---

## 13. Thread Safety

| Component | Policy |
|-----------|--------|
| VSOP87D const tables | Immutable — read-only, always safe |
| Nutation 106-term table | Immutable — always safe |
| Leap second table | Immutable — always safe |
| tzdb cache (global dict) | Single-write lazy init; reads safe after first init |
| `clock.now()`, `clock.monotonic()` | Kernel syscall — inherently safe |
| Tất cả value types (Copy) | No shared state — always safe |

Không cần lock trong hot path astronomy computation.

---

## 14. Design Decisions Log

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | Module mới ở `chrono/`, không overwrite `datetime/` cũ | Backward compatibility với consumer hiện tại |
| D2 | `Instant` dùng `i64 nanos` | Không precision loss; không year-2038 bug; đủ range ±292 năm |
| D3 | `Duration` signed i64 | Negative duration tự nhiên; không cần Optional cho "thời điểm quá khứ" |
| D4 | `AstroTime` split jdInt+jdFrac | JD≈2.461.000 → f64 đơn chỉ có precision ~0.3ms; split cho < 1μs |
| D5 | Angle canonical = radians | Tránh deg↔rad trong hot path; một representation duy nhất |
| D6 | VSOP87D là const arrays | Zero allocation; compile-time baked; L1/L2 cache-friendly |
| D7 | tzdb không embed vào binary | tzdata ~3MB gzipped; user cập nhật tzdb độc lập với compiler |
| D8 | `.to()` và `.reassign()` tên khác | Phân biệt "đổi timezone giữ instant" vs "gắn timezone vào local clock" |
| D9 | Moon backend riêng (Meeus Ch47) | VSOP87D là planetary theory, không phải lunar theory |
| D10 | Không hỗ trợ leap second ở TimeOfDay | Complexity không xứng use case phổ biến; documented |
| D11 | Year 0 tồn tại | ISO 8601 compliant; tránh off-by-one khi tính BCE |
| D12 | East longitude positive | Chuẩn thiên văn quốc tế; nhất quán toàn astro module |
| D13 | Month overflow policy: clamp | Deterministic; không ngạc nhiên; document rõ trước |
| D14 | tzdb search path thứ tự có $VIRON_TZ_PATH đầu | Cho phép test và override mà không cần root |

---

## 15. Extension Points

| Area | Cơ chế mở rộng |
|------|--------------|
| Lunar backend | `moon.vri` expose `MoonBackend` interface — swap Meeus → ELP2000, JPL DE |
| Ephemeris backend | `vsop/evaluator.vri` generic — thêm VSOP2013, DE430 không đổi `sun` API |
| Timezone source | `database.vri` có thể swap search path — embedded tzdata, remote fetch |
| Locale | `format.vri` accept `LocaleProvider` — thêm locale data không đổi core |
| Leap seconds | Static table trong `astro/time.vri` — update khi IERS announce |
| Precession model | Swap IAU 1976 → IAU 2006 → IAU 2020 không đổi caller API |
| Platform clock | `clock.vri` abstract over `sys_clock_gettime` — thêm platform mới dễ |

---

## 16. Reference Sources

| Nguồn | Dùng cho |
|-------|---------|
| Meeus, J. "Astronomical Algorithms" 2nd ed. (1998) | VSOP87D usage, GMST, nutation, solar terms, moon |
| Bretagnon & Francou (1988) A&A 202, 309 | VSOP87D coefficient tables |
| IAU SOFA Library (Standards of Fundamental Astronomy) | GMST/GAST, precession, nutation formulae |
| IERS Bulletins C | Leap second table, DUT1 |
| ISO 8601:2004 | Date/time format specification |
| RFC 3339 (Klyne & Newman 2002) | Internet timestamp format |
| RFC 8536 (Olson et al. 2019) | TZif binary format v1/v2/v3 |
| IANA Time Zone Database | tzdata content and alias structure |
| Capitaine et al. (2003) A&A 412, 567 | IAU 2006 precession |
| Wahr (1981) | IAU 1980 nutation coefficients |

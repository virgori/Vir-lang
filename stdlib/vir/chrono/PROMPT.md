# Vir Chrono — Design Prompt

> Prompt gốc yêu cầu thiết kế hệ thống Date/Time/Timezone/Astronomy cho Vir Programming Language.  
> Lưu tại: `stdlib/vir/chrono/PROMPT.md`  
> Ngày: 2026-09-17

---

Hãy triển khai một hệ thống **Date / Time / Timezone / Astronomy hoàn chỉnh cho Vir Programming Language**.

Đây không phải task làm MVP, demo, proof-of-concept hay "đủ dùng".
Mục tiêu là xây dựng một subsystem đủ nghiêm túc để trở thành **standard library chính thức của một ngôn ngữ lập trình hệ thống**, có API ổn định, đầy đủ, nhất quán, có thể sử dụng cho backend, hệ thống phân tán, scientific computing, astronomy, calendar engine và các ứng dụng lâu dài.

Không được cắt tính năng chỉ vì implementation phức tạp.

Không được để TODO giả, stub, placeholder, hardcode kết quả hoặc API tồn tại nhưng implementation rỗng.

Không được thiết kế API quanh một vài test case hiện tại.

Phải thiết kế theo hướng lâu dài.

---

# 1. MỤC TIÊU KIẾN TRÚC

Tách thành các subsystem độc lập nhưng tương thích:

```text
time
date
datetime
timezone
calendar
astro
astro/vsop
```

Luồng tổng thể:

```text
OS clock
    ↓
instant / duration
    ↓
date / time / datetime
    ↓
timezone
    ↓
calendar
    ↓
astronomical time
    ↓
Julian systems
    ↓
VSOP87D
    ↓
Sun / planets / coordinates / events
```

Không trộn logic hệ thống thời gian dân sự với logic astronomy.

Không nhét VSOP87D vào `date`.

---

# 2. QUY TẮC NAMING BẮT BUỘC

API phải theo phong cách Vir:

* không dùng `snake_case`
* không dùng dấu `_` trong public API
* module viết thường
* hàm viết thường hoặc `camelCase`
* property viết thường hoặc `camelCase`
* tránh identifier viết HOA toàn bộ
* tránh tên Java-style dài dòng
* tránh `getX`, `setX`, `calculateX`, `computeX` nếu context đã rõ
* ưu tiên từ ngắn nhưng rõ nghĩa
* không lặp lại context của module/type trong tên hàm

Ví dụ tốt:

```vir
datetime.now()
date.parse(...)
date.format(...)

time.min
time.sec

astro.sun(time)
astro.moon(time)
astro.planet(mars, time)

vsop.position(earth, time)

sun.longitude
sun.latitude
sun.declination
sun.rightAscension
sun.distance
```

Không dùng:

```vir
getCurrentDateTime()
calculatePlanetaryPosition()
getSolarDeclination()
calculateSolarEclipticLongitude()
```

Không viết tắt thuật ngữ astronomy khó hiểu:

```text
không:
ra
dec
lon
lat
dist
pos

nên:
rightAscension
declination
longitude
latitude
distance
position
```

Riêng các viết tắt cực kỳ quen thuộc trong date/time có thể dùng:

```text
min
sec
ms
```

Các chuẩn quốc tế như UTC, TAI, TT, UT1, TDB có thể xuất hiện trong tài liệu nhưng API Vir nên ưu tiên:

```vir
utc
tai
tt
ut1
tdb
```

Không thiết kế API dựa vào uppercase constant style.

---

# 3. CORE TIME

Triển khai abstraction thời gian hệ thống hoàn chỉnh.

Phải có:

```text
Instant
Duration
Clock
Time
```

## Instant

Đại diện cho một thời điểm tuyệt đối.

Phải hỗ trợ:

* Unix epoch
* seconds
* milliseconds
* microseconds
* nanoseconds nếu platform hỗ trợ
* conversion an toàn
* comparison
* ordering
* subtraction
* addition với Duration
* overflow checking
* negative timestamps
* timestamps trước 1970
* timestamps sau 2038
* kiến trúc 64-bit

Ví dụ API:

```vir
var now = instant.now()

var sec = now.seconds()
var ms = now.milliseconds()
```

## Clock

Phải có:

```text
wall clock
monotonic clock
high resolution clock
process clock nếu OS hỗ trợ
thread clock nếu OS hỗ trợ
```

Ví dụ:

```vir
clock.now()
clock.monotonic()
```

Không dùng wall clock để đo benchmark elapsed time.

## Duration

Duration phải hỗ trợ:

```text
nanosecond
microsecond
millisecond
second
minute
hour
day
week
```

Phải có:

* cộng
* trừ
* nhân
* chia
* compare
* absolute
* sign
* conversion
* checked conversion
* overflow detection

Ví dụ:

```vir
var span = 5.min + 30.sec
```

Nếu extension literal chưa hỗ trợ thì cung cấp constructor tương ứng.

---

# 4. DATE

Type `date` phải biểu diễn ngày dân sự không timezone.

Phải hỗ trợ đầy đủ:

```text
year
month
day
weekday
dayOfYear
weekOfYear
quarter
```

Phải xử lý đúng:

* leap year
* Gregorian calendar
* proleptic Gregorian
* BCE/CE nếu representation cho phép
* year 0 policy phải định nghĩa rõ
* month length
* validation

API tối thiểu:

```vir
date.create(...)
date.parse(...)
date.format(...)

date.year
date.month
date.day
date.weekday
date.dayOfYear
```

Phải hỗ trợ:

```text
addDays
addWeeks
addMonths
addYears
```

Phải xử lý edge cases:

```text
Jan 31 + 1 month
Feb 29 + 1 year
leap year transitions
month overflow
negative year nếu hỗ trợ
```

Policy phải nhất quán và được document rõ.

---

# 5. TIME OF DAY

Type `time` đại diện thời gian trong ngày.

Phải hỗ trợ:

```text
hour
min
sec
millisecond
microsecond
nanosecond
```

Validation:

```text
00:00:00
23:59:59
fractional seconds
```

Nếu hỗ trợ leap second phải định nghĩa rõ representation.

Không âm thầm giả định leap second tồn tại hay không tồn tại.

---

# 6. DATETIME

`datetime` = date + time nhưng chưa nhất thiết có timezone.

Phải có:

```vir
datetime.now()
datetime.create(...)
datetime.parse(...)
datetime.format(...)
```

Fields:

```text
year
month
day
hour
min
sec
millisecond
microsecond
nanosecond
weekday
dayOfYear
```

Operations:

```text
add
subtract
compare
diff
startOfDay
endOfDay
startOfMonth
endOfMonth
startOfYear
endOfYear
```

Không phụ thuộc timezone một cách ngầm định.

Phải phân biệt rõ:

```text
naive datetime
zoned datetime
absolute instant
```

Không được nhập nhằng ba khái niệm này.

---

# 7. PARSE VÀ FORMAT

Không chỉ hỗ trợ một format.

Phải xây parser/formatter thực sự.

Hỗ trợ ít nhất:

```text
ISO 8601
RFC 3339
RFC 2822 / RFC 5322 date forms nếu phù hợp
Unix timestamp
custom format patterns
```

ISO 8601 phải xử lý:

```text
calendar date
ordinal date
week date
timezone offsets
fractional seconds
UTC Z suffix
expanded years nếu có
```

Ví dụ:

```vir
datetime.parse("2026-09-17T10:30:00+07:00")
```

Formatting:

```vir
time.format("yyyy-MM-dd HH:mm:ss")
```

Phải hỗ trợ escape literal.

Không parse bằng regex đơn giản rồi bỏ qua edge case.

---

# 8. TIMEZONE

Phải triển khai timezone như subsystem thực sự.

Không được chỉ hỗ trợ numeric offset.

Phải hỗ trợ IANA Time Zone Database.

Ví dụ:

```vir
var local = now.to("Asia/Ho_Chi_Minh")
var tokyo = now.to("Asia/Tokyo")
```

Phải hỗ trợ:

```text
timezone names
UTC offsets
historical offsets
DST
DST transition
ambiguous local time
nonexistent local time
timezone aliases
timezone normalization
```

Phải xử lý đúng các tình huống:

```text
clock moves forward
clock moves backward
same local time occurs twice
local time does not exist
historical timezone change
government changes DST rules
```

API phải cho phép caller chọn policy khi local time ambiguous:

```text
earlier
later
reject
```

Và khi local time nonexistent:

```text
forward
backward
reject
```

Không silently chọn một kết quả mà không document.

---

# 9. TZ DATABASE

Không hardcode toàn bộ tzdata vào compiler source.

Thiết kế timezone database thành component độc lập.

Nên cho phép Viron quản lý:

```text
install
update
version
verify
```

Runtime phải biết:

```text
tz database version
timezone lookup
aliases
transition tables
```

API phải hoạt động ổn định dù tzdata update độc lập với compiler.

---

# 10. ZONED DATETIME

Phải có abstraction riêng cho datetime có timezone.

Ví dụ concept:

```text
zoned
```

Phải giữ:

```text
local date
local time
timezone
offset
instant
```

Conversion:

```vir
var tokyo = local.to("Asia/Tokyo")
```

Timezone conversion phải giữ cùng instant.

Timezone reassignment phải là operation khác timezone conversion.

Không để API dễ gây nhầm giữa:

```text
"đổi timezone"
và
"gắn timezone mới vào cùng local clock"
```

---

# 11. CALENDAR UTILITIES

Phải có calendar utility đủ mạnh.

Bao gồm:

```text
daysInMonth
daysInYear
leapYear
weekday
weekNumber
ISO week
ordinal date
quarter
start/end boundaries
```

Phải hỗ trợ ISO week-year đúng chuẩn.

---

# 12. LOCALE

Thiết kế layer locale riêng.

Ít nhất architecture phải cho phép:

```text
month names
weekday names
date formats
time formats
12h / 24h
AM / PM
localized output
```

Không hardcode English trực tiếp vào core date algorithms.

Nếu locale data chưa bundled toàn bộ, architecture vẫn phải đúng để mở rộng sau này.

---

# 13. ASTRONOMICAL TIME

Tạo subsystem `astro.time`.

Phải có các time scale:

```text
utc
tai
tt
ut1
tdb
```

Phải hiểu rõ chúng không giống nhau.

Không convert tất cả bằng cùng một offset giả.

Phải thiết kế nguồn dữ liệu cho:

```text
leap seconds
DUT1
Delta T
```

Phân biệt:

```text
UTC
atomic time
terrestrial time
Earth rotation time
barycentric dynamical time
```

---

# 14. JULIAN TIME SYSTEMS

Phải hỗ trợ:

```text
Julian Date
Modified Julian Date
Julian century
Julian millennium
J2000 epoch
```

Tên property phải rõ:

```vir
time.julianDate
time.modifiedJulianDate
```

Không chỉ cung cấp tên viết tắt khó đọc.

Phải support conversion hai chiều:

```text
datetime -> Julian Date
Julian Date -> datetime
```

với time scale xác định rõ.

---

# 15. VSOP87D

Nhúng đầy đủ VSOP87D vào thư viện astronomy riêng.

Không giảm coefficient để "demo".

Không bỏ planet vì data lớn.

Không thay VSOP87D bằng approximation ngắn.

Phải hỗ trợ các thiên thể thuộc bộ VSOP87D:

```text
Mercury
Venus
Earth
Mars
Jupiter
Saturn
Uranus
Neptune
```

Nếu Pluto không thuộc VSOP87D thì không giả vờ thêm vào cùng backend.

Data phải được tổ chức hiệu quả:

```text
constant tables
read-only data
compile-time optimized
cache friendly
```

Không parse JSON runtime.

Không dùng text data runtime nếu có thể compile thành static tables.

Public API:

```vir
vsop.position(earth, time)
```

Return structure phải có ít nhất:

```text
longitude
latitude
radius
```

và metadata/unit rõ ràng.

---

# 16. VSOP EVALUATOR

Triển khai evaluator đúng công thức:

```text
sum A * cos(B + C * t)
```

theo từng series order.

Phải support đầy đủ các series của:

```text
L
B
R
```

Không hardcode Earth-only.

Phải có:

```text
series evaluation
time normalization
angle normalization
unit conversion
precision validation
```

---

# 17. SUN

Tạo high-level API:

```vir
astro.sun(time)
```

Không bắt user tự lấy Earth rồi đảo vector.

Sun result phải có ít nhất:

```text
longitude
latitude
distance
rightAscension
declination
```

Nếu có thể phải hỗ trợ cả:

```text
geometric
apparent
mean
true
```

và phải phân biệt rõ.

---

# 18. PLANETS

API:

```vir
astro.planet(mars, time)
```

Phải trả đầy đủ:

```text
heliocentric coordinates
geocentric coordinates
ecliptic coordinates
equatorial coordinates
distance from Sun
distance from Earth
longitude
latitude
rightAscension
declination
```

Không gọi tất cả là `position` nếu chúng thuộc reference frame khác nhau mà không metadata.

---

# 19. COORDINATE SYSTEMS

Astronomy library phải hỗ trợ abstraction coordinate rõ ràng:

```text
ecliptic
equatorial
horizontal
heliocentric
geocentric
topocentric
```

Các transform cần có:

```text
ecliptic -> equatorial
equatorial -> ecliptic
equatorial -> horizontal
horizontal -> equatorial
```

Phải xử lý:

```text
obliquity
sidereal time
observer location
parallax khi cần
```

---

# 20. ANGLES

Tạo abstraction hoặc utility cho angle.

Phải hỗ trợ:

```text
degree
radian
hour angle
arcminute
arcsecond
```

Normalization:

```text
0..360
-180..180
0..24h
```

Không rải manual `% 360` khắp codebase.

---

# 21. OBSERVER / SITE

Tạo type biểu diễn vị trí quan sát.

Tên nên ngắn và rõ, ví dụ:

```vir
site
```

Fields:

```text
latitude
longitude
elevation
```

Phải xác định convention longitude:

```text
east positive
hoặc
west positive
```

và dùng nhất quán.

Không được có module khác dùng convention ngược lại.

---

# 22. SIDEREAL TIME

Phải hỗ trợ:

```text
Greenwich mean sidereal time
Greenwich apparent sidereal time
local sidereal time
```

Public API không nên dùng acronym khó hiểu.

---

# 23. PRECESSION

Phải có module precession.

Hỗ trợ chuyển tọa độ giữa epochs.

Ít nhất:

```text
J2000
date epoch
custom Julian epoch
```

Không giả định tất cả tọa độ luôn J2000.

---

# 24. NUTATION

Phải hỗ trợ nutation:

```text
longitude
obliquity
```

và áp dụng khi tính apparent position.

Không dùng một constant obliquity cho mọi thời điểm.

---

# 25. ABERRATION

Thiết kế correction cho:

```text
annual aberration
light-time nếu cần
```

Không trộn geometric position và apparent position.

---

# 26. ATMOSPHERIC REFRACTION

Horizontal astronomy phải hỗ trợ refraction.

Cần có:

```text
standard atmosphere defaults
pressure
temperature
optional correction
```

Refraction phải có thể bật/tắt.

---

# 27. SUNRISE / SUNSET

Phải triển khai:

```vir
astro.rise(sun, date, site)
astro.set(sun, date, site)
```

Nhưng implementation phải đủ cho:

```text
sunrise
sunset
solar noon
civil twilight
nautical twilight
astronomical twilight
```

Phải xử lý:

```text
polar day
polar night
no rise
no set
```

Không trả timestamp giả trong trường hợp event không tồn tại.

---

# 28. PLANET RISE / SET

Architecture rise/set không được hardcode riêng cho Sun.

Phải có khả năng dùng cho:

```text
Sun
Moon
planets
```

---

# 29. SOLAR LONGITUDE

Phải hỗ trợ tính hoàng kinh Mặt Trời.

API:

```vir
astro.sun(time).longitude
```

và event search:

```vir
astro.atLongitude(...)
```

Phải tìm thời điểm chính xác khi Sun đạt longitude mục tiêu.

Không chỉ kiểm tra ngày gần nhất.

---

# 30. SOLAR TERMS

Triển khai 24 tiết khí.

API gọn:

```vir
astro.term(time)
```

Phải trả:

```text
index
name
longitude
start
end
```

và có khả năng:

```text
term hiện tại
term tiếp theo
term trước đó
tìm term trong năm
```

24 mốc:

```text
0°
15°
30°
...
345°
```

Phải thống nhất mapping tên.

Không hardcode theo timezone địa phương.

Core astronomical event phải là instant; local date được chuyển sau.

---

# 31. EQUINOX VÀ SOLSTICE

API:

```vir
astro.equinox(year)
astro.solstice(year)
```

Nhưng phải phân biệt:

```text
March equinox
June solstice
September equinox
December solstice
```

Không chỉ trả một event mơ hồ.

---

# 32. SEASON EVENTS

Cho phép lấy toàn bộ season boundaries trong năm.

Kết quả phải là astronomical instant.

Timezone conversion làm ở layer datetime/timezone.

---

# 33. MOON ARCHITECTURE

Dù VSOP87D không phải lunar theory, `astro` phải được thiết kế để Moon là backend độc lập.

Không ép Moon vào VSOP.

Architecture phải cho phép thêm model lunar như:

```text
ELP
Meeus lunar terms
JPL ephemerides
```

Public API:

```vir
astro.moon(time)
```

---

# 34. MOON OUTPUT

Moon API phải có khả năng trả:

```text
longitude
latitude
distance
rightAscension
declination
phase angle
illumination
age
```

Nếu model chưa triển khai ngay thì architecture vẫn phải tách đúng backend.

Không fake precision.

---

# 35. LUNAR PHASE

Phải hỗ trợ event:

```text
new moon
first quarter
full moon
last quarter
```

Phải tìm instant event.

Không xác định phase đơn thuần bằng ngày âm lịch.

---

# 36. ROOT FINDING

Astronomical event search cần utility numerical riêng.

Phải hỗ trợ ít nhất:

```text
bisection
Newton-Raphson khi derivative phù hợp
secant
hybrid solver
```

Phải có:

```text
tolerance
max iterations
convergence check
bracketing
failure result
```

Không dùng vòng lặp magic-number khắp từng astronomy function.

---

# 37. NUMERICAL PRECISION

Mọi astronomy calculation phải dùng precision phù hợp.

Không dùng `f32` cho VSOP hoặc Julian time nếu gây mất chính xác.

Mặc định dùng:

```text
f64
```

Phải kiểm tra:

```text
catastrophic cancellation
angle normalization
large Julian dates
precision around event roots
```

---

# 38. UNITS

Không được nhập nhằng unit.

Mọi field phải định nghĩa rõ:

```text
degree
radian
AU
kilometer
meter
second
day
```

Nếu API dùng degree mặc định thì phải nhất quán.

Không có chỗ dùng degree, chỗ khác dùng radian mà tên giống nhau.

---

# 39. ERROR MODEL

Không trả sentinel value như:

```text
-1
999
NaN
```

để biểu diễn lỗi nghiệp vụ nếu Vir có cơ chế result/error tốt hơn.

Phải phân biệt:

```text
invalid input
timezone missing
timezone ambiguous
timezone nonexistent
event not found
event does not occur
out of model range
numerical convergence failure
```

---

# 40. RANGE

Mỗi algorithm phải có valid range rõ.

VSOP87D phải expose/document phạm vi precision phù hợp.

Không claim precision ngoài range dữ liệu.

---

# 41. PERFORMANCE

Date/time core phải nhẹ.

Timezone lookup phải cache được.

VSOP evaluation phải tối ưu:

```text
static data
contiguous memory
minimal allocation
arena compatible
no hidden heap churn
```

Không tạo allocation cho từng term trong VSOP loop.

Không dùng dynamic map trong hot path nếu dữ liệu tĩnh.

---

# 42. NO GC ASSUMPTION

Vir là ngôn ngữ native không dựa vào GC.

Mọi API phải phù hợp với memory model của Vir.

Không thiết kế API theo giả định JavaScript/Python garbage collector.

Temporary astronomy data phải phù hợp:

```text
stack
arena
sub-arena
borrowed references
immutable static data
```

---

# 43. THREAD SAFETY

Các static tables phải immutable.

Timezone database cache phải thread-safe.

Không dùng global mutable state không đồng bộ.

---

# 44. DETERMINISM

Cùng:

```text
instant
timezone database version
astronomy data version
input
```

phải cho cùng output.

Không phụ thuộc locale hoặc machine timezone ngầm định.

---

# 45. SYSTEM TIMEZONE

Cho phép lấy:

```text
system timezone
current offset
timezone identifier
```

nhưng không giả định system timezone luôn có IANA name.

Phải xử lý fallback.

---

# 46. SERIALIZATION

Các type date/time phải có canonical representation.

Hỗ trợ:

```text
ISO serialization
timestamp serialization
timezone serialization
```

Không serialize internal struct memory trực tiếp.

---

# 47. HASH VÀ COMPARISON

Các type phù hợp phải hỗ trợ:

```text
equality
ordering
hash
```

Phải định nghĩa comparison semantics của:

```text
instant
datetime
zoned datetime
date
time
duration
```

---

# 48. IMMUTABILITY

Date/time value type nên ưu tiên immutable semantic.

Các operation như:

```text
add
subtract
to
```

trả value mới.

Không mutate object âm thầm.

---

# 49. TEST SUITE

Phải có test toàn diện.

Không chỉ test happy path.

Date:

```text
leap years
century rule
400-year rule
month boundaries
BCE nếu hỗ trợ
```

Timezone:

```text
DST forward
DST backward
ambiguous time
nonexistent time
historical transitions
```

Julian:

```text
known reference dates
J2000
round trip
```

VSOP:

```text
known reference values
multiple planets
multiple dates
L/B/R validation
```

Astronomy:

```text
equinox
solstice
solar longitude
solar terms
rise/set
coordinate transforms
```

---

# 50. REFERENCE TEST DATA

Đối chiếu với reference sources đáng tin cậy.

Không tự tạo expected value từ chính implementation đang test.

Test data cần ghi:

```text
source
epoch
unit
precision tolerance
```

---

# 51. API DOCUMENTATION

Mỗi public API phải document:

```text
input
output
unit
timezone assumption
time scale
coordinate frame
range
precision
error behavior
```

Astronomy tuyệt đối không được document mơ hồ.

---

# 52. MODULE STRUCTURE

Không dồn tất cả vào một file lớn.

Gợi ý:

```text
std/
  time/
    instant.vri
    duration.vri
    clock.vri

  date/
    date.vri
    time.vri
    datetime.vri
    parse.vri
    format.vri
    calendar.vri

  timezone/
    zone.vri
    zoned.vri
    database.vri
    transition.vri

  astro/
    time.vri
    julian.vri
    angle.vri
    site.vri
    coordinates.vri
    sidereal.vri
    precession.vri
    nutation.vri
    refraction.vri
    event.vri
    sun.vri
    planet.vri
    moon.vri
    term.vri

    vsop/
      types.vri
      evaluator.vri
      mercury.vri
      venus.vri
      earth.vri
      mars.vri
      jupiter.vri
      saturn.vri
      uranus.vri
      neptune.vri
```

Có thể điều chỉnh structure nếu codebase Vir hiện tại có convention khác, nhưng phải giữ SRP.

---

# 53. PUBLIC API KHÔNG LỘ BACKEND

`astro.sun()` không được phụ thuộc public contract vào VSOP87D.

VSOP87D chỉ là backend.

Sau này phải có thể thay hoặc thêm:

```text
VSOP2013
JPL DE
ELP
```

mà không phá:

```vir
astro.sun(...)
astro.planet(...)
astro.moon(...)
```

---

# 54. DATA VERSIONING

Astronomy data và timezone data phải có version metadata.

Ví dụ concept:

```text
timezone database version
vsop data version
leap second table version
DUT1 source version
```

Không cần expose mọi thứ ở top-level nhưng phải truy xuất được để debug và reproducibility.

---

# 55. KHÔNG PHỤ THUỘC LIBC NẾU KHÔNG CẦN

Vir đã có runtime/syscall layer.

Date/time core cần dùng abstraction OS thích hợp.

Không thêm dependency libc chỉ để lấy thời gian nếu Vir runtime đã có syscall native phù hợp.

Phải support Linux/macOS ARM64 theo kiến trúc hiện tại và để đường mở rộng cho các platform khác.

---

# 56. KHÔNG COPY API JAVASCRIPT MÙ QUÁNG

Có thể tham khảo khả năng của:

```text
JavaScript Temporal
Rust time / chrono
Java java.time
Python datetime
Swift Foundation
C++ chrono
```

nhưng API cuối phải mang triết lý Vir.

Không kế thừa lỗi thiết kế legacy của JavaScript `Date`.

---

# 57. YÊU CẦU CUỐI CÙNG

Trước khi code:

1. kiểm tra kiến trúc stdlib hiện tại của Vir
2. kiểm tra naming convention hiện tại
3. kiểm tra memory model
4. kiểm tra error/result mechanism
5. kiểm tra module/import convention
6. kiểm tra numeric types
7. kiểm tra operator overload hiện có
8. kiểm tra runtime syscall time hiện có
9. kiểm tra package/component integration với Viron

Sau đó mới triển khai.

Không tạo syntax mà Vir chưa hỗ trợ.

Không tự phát minh language feature để làm implementation trông đẹp hơn.

Nếu API mong muốn cần feature compiler chưa có, phải:

```text
a. dùng syntax hợp lệ hiện tại
b. ghi rõ limitation
c. tách proposal compiler feature riêng
```

Không sửa compiler ngoài phạm vi task nếu chưa thực sự cần.

---

# DEFINITION OF DONE

Task chỉ được xem là hoàn tất khi:

```text
Date hoạt động đầy đủ
Time hoạt động đầy đủ
DateTime hoạt động đầy đủ
Duration hoạt động đầy đủ
Clock hoạt động đầy đủ
Timezone hoạt động với IANA tzdb
DST edge cases được xử lý
parse/format đầy đủ
Julian conversion hoàn chỉnh
astronomical time scale architecture hoàn chỉnh
VSOP87D đầy đủ 8 planet
Sun high-level API hoạt động
Planet high-level API hoạt động
coordinate transforms hoạt động
sidereal time hoạt động
precession/nutation architecture hoạt động
solar longitude hoạt động
24 solar terms hoạt động
equinox/solstice hoạt động
rise/set framework hoạt động
Moon backend architecture độc lập
numerical root solver hoàn chỉnh
tests bao phủ edge cases
documentation đầy đủ
không còn stub
không còn TODO quan trọng
không còn hardcode test-specific
không có public API snake_case
không có astronomy acronym khó hiểu
không có module khổng lồ vi phạm SRP
```

Không được dừng khi "compile được".

Không được dừng khi "test chính pass".

Không được dừng ở MVP.

Hãy hoàn thiện subsystem theo tiêu chuẩn production-quality standard library.

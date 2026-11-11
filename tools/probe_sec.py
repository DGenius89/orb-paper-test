import io, sys, urllib.request, zipfile
UA = "DGenius89 orb-paper-test research (https://github.com/DGenius89/orb-paper-test)"
q = sys.argv[1] if len(sys.argv) > 1 else "2024q1"
url = f"https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"
req = urllib.request.Request(url, headers={"User-Agent": UA})
try:
    raw = urllib.request.urlopen(req, timeout=120).read()
except Exception as e:
    print("FETCH FAIL", url, e); sys.exit(0)
z = zipfile.ZipFile(io.BytesIO(raw))
print(url, len(raw) // 1e6, "MB")
for n in z.namelist():
    with z.open(n) as fh:
        lines = [fh.readline().decode("utf-8", "replace").rstrip() for _ in range(3)]
    print("==", n); [print("  ", l[:400]) for l in lines]

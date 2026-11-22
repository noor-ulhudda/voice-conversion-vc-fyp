import re, glob, shutil
p = glob.glob("/opt/seed-vc/modules/**/bigvgan.py", recursive=True)[0]
shutil.copy(p, p + ".bak"); s = open(p).read()
s = re.sub(r"proxies:\s*Optional\[Dict\],", "proxies: Optional[Dict] = None,", s)
s = re.sub(r"resume_download:\s*bool,", "resume_download: bool = False,", s)
s = re.sub(r"^\s*proxies\s*=\s*proxies,\s*\n", "", s, flags=re.M)
s = re.sub(r"^\s*resume_download\s*=\s*resume_download,\s*\n", "", s, flags=re.M)
open(p, "w").write(s); print("bigvgan patched")

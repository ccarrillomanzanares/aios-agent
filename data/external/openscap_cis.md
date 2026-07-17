# OpenSCAP y benchmarks CIS

OpenSCAP evalúa cumplimiento de seguridad.

## Instalación
```bash
sudo apt install libopenscap8 scap-security-guide
```

## Evaluar
```bash
sudo oscap xccdf eval --profile xccdf_org.ssgproject.content_profile_standard --report /tmp/report.html /usr/share/xml/scap/ssg/content/ssg-ubuntu2204-ds.xml
```

## Remediación
```bash
sudo oscap xccdf generate fix --profile xccdf_org.ssgproject.content_profile_standard --fix-type bash /usr/share/xml/scap/ssg/content/ssg-ubuntu2204-ds.xml > /tmp/remediate.sh
```

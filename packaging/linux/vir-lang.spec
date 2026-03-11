%global vir_version 0.3.0
%global vir_release 1

Name:           vir-lang
Version:        %{vir_version}
Release:        %{vir_release}%{?dist}
Summary:        Vir Programming Language — Multilingual syntax, JIT, self-patching binary

License:        MIT
URL:            https://github.com/vir-lang/vir
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  python3-devel >= 3.11
BuildRequires:  python3-setuptools
Requires:       python3 >= 3.11
Requires:       python3-regex
Requires:       glibc

%description
Vir is a structured, block-scoped programming language with
Vietnamese-first syntax and multilingual support (EN, ZH, JA, KO).
Features include JIT compilation, Q-IR virtual machine,
SIMD-accelerated native core, and self-patching binary backend.

%prep
%autosetup -n %{name}-%{version}

%build
# Build native library
cd core
make clean
make all
cd ..

# Build Python wheel
python3 -m pip install --user build setuptools wheel
mkdir -p src/native/lib
cp core/lib/libvir_core.so src/native/lib/ 2>/dev/null || true
cp core/lib/libvir_core.a  src/native/lib/ 2>/dev/null || true
python3 -m build --wheel --outdir dist/

%install
rm -rf %{buildroot}

# Directories
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_libdir}
install -d %{buildroot}%{_datadir}/vir/stdlib
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}%{_tmpfilesdir}
install -d %{buildroot}%{_sysconfdir}/vir
install -d %{buildroot}%{python3_sitelib}

# Native libraries
install -m 0755 core/lib/libvir_core.so %{buildroot}%{_libdir}/ 2>/dev/null || true
install -m 0644 core/lib/libvir_core.a  %{buildroot}%{_libdir}/ 2>/dev/null || true

# CLI binary
install -m 0755 core/build/vir %{buildroot}%{_bindir}/vir-native 2>/dev/null || true

# Python package (install wheel)
pip3 install --root=%{buildroot} --prefix=%{_prefix} --no-deps dist/*.whl

# Stdlib
cp -r stdlib/* %{buildroot}%{_datadir}/vir/stdlib/ 2>/dev/null || true

# Config / systemd
install -m 0644 packaging/linux/vir.conf          %{buildroot}%{_sysconfdir}/vir/
install -m 0644 packaging/linux/vir.service        %{buildroot}%{_unitdir}/
install -m 0644 packaging/linux/vir-tmpfiles.conf  %{buildroot}%{_tmpfilesdir}/vir.conf

# Wrapper scripts
cat > %{buildroot}%{_bindir}/vir << 'EOF'
#!/bin/bash
exec python3 -m src.runtime.lifecycle "$@"
EOF
chmod 755 %{buildroot}%{_bindir}/vir

cat > %{buildroot}%{_bindir}/viron << 'EOF'
#!/bin/bash
exec python3 -m src.viron.cli "$@"
EOF
chmod 755 %{buildroot}%{_bindir}/viron

%pre
getent group vir >/dev/null 2>&1 || groupadd -r vir
getent passwd vir >/dev/null 2>&1 || \
    useradd -r -g vir -d /var/lib/vir -s /sbin/nologin \
    -c "Vir Language Runtime" vir

%post
/sbin/ldconfig
%systemd_post vir.service
install -d -m 0750 -o vir -g vir /var/lib/vir
install -d -m 0750 -o vir -g vir /var/log/vir
install -d -m 0750 -o vir -g vir /var/cache/vir

%preun
%systemd_preun vir.service

%postun
/sbin/ldconfig
%systemd_postun_with_restart vir.service

%files
%license LICENSE
%doc README.md
%config(noreplace) %{_sysconfdir}/vir/vir.conf
%{_bindir}/vir
%{_bindir}/viron
%{_bindir}/vir-native
%{_libdir}/libvir_core.so
%{_libdir}/libvir_core.a
%{_unitdir}/vir.service
%{_tmpfilesdir}/vir.conf
%{_datadir}/vir/
%{python3_sitelib}/src/
%{python3_sitelib}/vir_lang-*.dist-info/

%changelog
* Wed Jan 01 2025 Vir Team <team@vir-lang.dev> - 0.3.0-1
- Phase 14: Production features (PQ, DiskANN, Hybrid Search, Metrics)
- Phase 13: Horizontal scaling (Consistent Hash, Replication)
- 157 unit tests, 23 benchmarks

* Wed Dec 01 2024 Vir Team <team@vir-lang.dev> - 0.2.0-1
- Initial RPM packaging
- Q-IR VM, JIT compilation, SIMD native core
- Multilingual support (vi, en, zh, ja, ko)

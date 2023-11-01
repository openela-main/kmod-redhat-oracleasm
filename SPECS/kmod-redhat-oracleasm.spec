%define kmod_name		oracleasm
%define kmod_vendor		redhat
%define kmod_rpm_name		kmod-redhat-oracleasm
%define kmod_driver_version	2.0.8
%define kmod_driver_epoch	8
%define kmod_rpm_release	17
%define kmod_kernel_version	4.18.0-444.el8
%define kmod_kernel_version_min	4.18.0-444.el8
%define kmod_kernel_version_dep	4.18.0
%define kmod_kbuild_dir		drivers/block/oracleasm
%define kmod_install_path	extra/kmod-redhat-oracleasm
%define kernel_pkg		kernel
%define kernel_devel_pkg	kernel-devel
%define kernel_modules_pkg	kernel-modules

%{!?dist: %define dist .el8_4}
%{!?make_build: %define make_build make}

%if "%{kmod_kernel_version_dep}" == ""
%define kmod_kernel_version_dep %{kmod_kernel_version}
%endif


Source0:	%{kmod_name}-%{kmod_vendor}-%{kmod_driver_version}.tar.bz2
# Source code patches
Patch0:	0000-Makefile-config-opts.patch
#Patch1:	0001-oracleasm-driver-replace-fs_context-with-mount_pseud.patch
Patch2:	0002-oracleasm-driver-make-bio_for_each_segment_all-worki.patch
Patch3:	0003-oracleasm-copy-rhel8-s-bio_map_user_iov.patch
Patch4:	0004-update-bdi-writeback-acct_dirty-flags.patch

%define findpat %( echo "%""P" )
%define __find_requires /usr/lib/rpm/redhat/find-requires.ksyms
%define __find_provides /usr/lib/rpm/redhat/find-provides.ksyms %{kmod_name} %{?epoch:%{epoch}:}%{version}-%{release}
%define sbindir %( if [ -d "/sbin" -a \! -h "/sbin" ]; then echo "/sbin"; else echo %{_sbindir}; fi )
%define dup_state_dir %{_localstatedir}/lib/rpm-state/kmod-dups
%define kver_state_dir %{dup_state_dir}/kver
%define kver_state_file %{kver_state_dir}/%{kmod_kernel_version}.%(arch)
%define dup_module_list %{dup_state_dir}/rpm-kmod-%{kmod_name}-modules

Name:		kmod-redhat-oracleasm
Version:	%{kmod_driver_version}
Release:	%{kmod_rpm_release}%{?dist}
%if "%{kmod_driver_epoch}" != ""
Epoch:		%{kmod_driver_epoch}
%endif
Summary:	oracleasm kernel module
Group:		System/Kernel
License:	GPLv2
URL:		https://github.com/oracle/linux-uek/tree/uek6/master/drivers/block/oracleasm
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
BuildRequires:	%kernel_devel_pkg = %kmod_kernel_version
BuildRequires:	redhat-rpm-config kernel-abi-whitelists elfutils-libelf-devel kernel-rpm-macros kmod
ExclusiveArch:	x86_64
%global kernel_source() /usr/src/kernels/%{kmod_kernel_version}.$(arch)

%global _use_internal_dependency_generator 0
Provides:	%kernel_modules_pkg >= %{kmod_kernel_version_min}.%{_target_cpu}
Provides:	kmod-%{kmod_name} = %{?epoch:%{epoch}:}%{version}-%{release}
Provides:	%{kmod_name} = %{?epoch:%{epoch}:}%{version}-%{release}
Provides:	%{kmod_name}-kmod = %{?epoch:%{epoch}:}%{version}-%{release}
Requires(post):	%{sbindir}/weak-modules
Requires(postun):	%{sbindir}/weak-modules
Requires:	kernel >= 4.18.0-240.el8
# if there are multiple kmods for the same driver from different vendors,
# they should conflict with each other.
Conflicts:	kmod-%{kmod_name}
Obsoletes:	%{name}-kernel_4_18_0_240
Obsoletes:	%{name}-kernel_4_18_0_240_14_1
Obsoletes:	%{name}-kernel_4_18_0_425_3_1
Obsoletes:	%{name}-kernel_4_18_0_425_10_1

%description
oracleasm kernel module

%post
modules=( $(find /lib/modules/%{kmod_kernel_version}.%(arch)/%{kmod_install_path} | grep '\.ko$') )
printf '%s\n' "${modules[@]}" | %{sbindir}/weak-modules --add-modules --no-initramfs

mkdir -p "%{kver_state_dir}"
touch "%{kver_state_file}"

exit 0

%posttrans
# We have to re-implement part of weak-modules here because it doesn't allow
# calling initramfs regeneration separately
if [ -f "%{kver_state_file}" ]; then
	kver_base="%{kmod_kernel_version_dep}"
	kvers=$(ls -d "/lib/modules/${kver_base%%.*}"*)

	for k_dir in $kvers; do
		k="${k_dir#/lib/modules/}"

		tmp_initramfs="/boot/initramfs-$k.tmp"
		dst_initramfs="/boot/initramfs-$k.img"

		# The same check as in weak-modules: we assume that the kernel present
		# if the symvers file exists.
		if [ -e "/boot/symvers-$k.gz" ] || [ -e "$k_dir/symvers.gz" ]; then
			/usr/bin/dracut -f "$tmp_initramfs" "$k" || exit 1
			cmp -s "$tmp_initramfs" "$dst_initramfs"
			if [ "$?" = 1 ]; then
				mv "$tmp_initramfs" "$dst_initramfs"
			else
				rm -f "$tmp_initramfs"
			fi
		fi
	done

	rm -f "%{kver_state_file}"
	rmdir "%{kver_state_dir}" 2> /dev/null
fi

rmdir "%{dup_state_dir}" 2> /dev/null

exit 0

%preun
if rpm -q --filetriggers kmod 2> /dev/null| grep -q "Trigger for weak-modules call on kmod removal"; then
	mkdir -p "%{kver_state_dir}"
	touch "%{kver_state_file}"
fi

mkdir -p "%{dup_state_dir}"
rpm -ql kmod-redhat-oracleasm-%{kmod_driver_version}-%{kmod_rpm_release}%{?dist}.$(arch) | \
	grep '\.ko$' > "%{dup_module_list}"

%postun
if rpm -q --filetriggers kmod 2> /dev/null| grep -q "Trigger for weak-modules call on kmod removal"; then
	initramfs_opt="--no-initramfs"
else
	initramfs_opt=""
fi

modules=( $(cat "%{dup_module_list}") )
rm -f "%{dup_module_list}"
printf '%s\n' "${modules[@]}" | %{sbindir}/weak-modules --remove-modules $initramfs_opt

rmdir "%{dup_state_dir}" 2> /dev/null

exit 0

%files
%defattr(644,root,root,755)
/lib/modules/%{kmod_kernel_version}.%(arch)
/etc/depmod.d/%{kmod_name}.conf
%doc /usr/share/doc/%{kmod_rpm_name}/greylist.txt



%prep
%setup -n %{kmod_name}-%{kmod_vendor}-%{kmod_driver_version}

%patch0 -p1
#%patch1 -p1
%patch2 -p1
%patch3 -p1
%patch4 -p1
set -- *
mkdir source
mv "$@" source/
mkdir obj

%build
rm -rf obj
cp -r source obj

PWD_PATH="$PWD"
%if "%{workaround_no_pwd_rel_path}" != "1"
PWD_PATH=$(realpath --relative-to="%{kernel_source}" . 2>/dev/null || echo "$PWD")
%endif
%{make_build} -C %{kernel_source} V=1 M="$PWD_PATH/obj/%{kmod_kbuild_dir}" \
	NOSTDINC_FLAGS="-I$PWD_PATH/obj/include -I$PWD_PATH/obj/include/uapi %{nil}" \
	EXTRA_CFLAGS="%{nil}" \
	%{nil}
# mark modules executable so that strip-to-file can strip them
find obj/%{kmod_kbuild_dir} -name "*.ko" -type f -exec chmod u+x '{}' +

whitelist="/lib/modules/kabi-current/kabi_whitelist_%{_target_cpu}"
for modules in $( find obj/%{kmod_kbuild_dir} -name "*.ko" -type f -printf "%{findpat}\n" | sed 's|\.ko$||' | sort -u ) ; do
	# update depmod.conf
	module_weak_path=$(echo "$modules" | sed 's/[\/]*[^\/]*$//')
	if [ -z "$module_weak_path" ]; then
		module_weak_path=%{name}
	else
		module_weak_path=%{name}/$module_weak_path
	fi
	echo "override $(echo $modules | sed 's/.*\///')" \
	     "$(echo "%{kmod_kernel_version_dep}" |
	        sed 's/\.[^\.]*$//;
		     s/\([.+?^$\/\\|()\[]\|\]\)/\\\0/g').*" \
		     "weak-updates/$module_weak_path" >> source/depmod.conf

	# update greylist
	nm -u obj/%{kmod_kbuild_dir}/$modules.ko | sed 's/.*U //' |  sed 's/^\.//' | sort -u | while read -r symbol; do
		grep -q "^\s*$symbol\$" $whitelist || echo "$symbol" >> source/greylist
	done
done
sort -u source/greylist | uniq > source/greylist.txt

%install
export INSTALL_MOD_PATH=$RPM_BUILD_ROOT
export INSTALL_MOD_DIR=%{kmod_install_path}
PWD_PATH="$PWD"
%if "%{workaround_no_pwd_rel_path}" != "1"
PWD_PATH=$(realpath --relative-to="%{kernel_source}" . 2>/dev/null || echo "$PWD")
%endif
make -C %{kernel_source} modules_install \
	M=$PWD_PATH/obj/%{kmod_kbuild_dir}
# Cleanup unnecessary kernel-generated module dependency files.
find $INSTALL_MOD_PATH/lib/modules -iname 'modules.*' -exec rm {} \;

install -m 644 -D source/depmod.conf $RPM_BUILD_ROOT/etc/depmod.d/%{kmod_name}.conf
install -m 644 -D source/greylist.txt $RPM_BUILD_ROOT/usr/share/doc/%{kmod_rpm_name}/greylist.txt


%clean
rm -rf $RPM_BUILD_ROOT

%changelog
* Wed Jan 04 2023 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-17
- Rebuild against kernel-4.18.0-444.el8 (#2148239).

* Mon Dec 12 2022 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-16
- Rebuild against kernel-4.18.0-440.el8 (#2148239).

* Mon Aug 29 2022 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-15
- Rebuild against kernel-4.18.0-423.el8 (#2117753).

* Mon Jul 18 2022 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-14
- Add Obsoletes: tag for old kernel-specific sub-packages (#1974732).

* Mon Feb 21 2022 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-13
- Update bdi->capabilities assignment due to change in the value semantics
  (#2060479).

* Tue Jul 13 2021 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-12
- Rebuild against kernel-4.18.0-321.el8.

* Thu Feb 11 2021 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-11
- Rebuild against kernel-4.18.0-286.el8.

* Mon Feb 08 2021 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-10
- Rebuild against kernel-4.18.0-282.el8 (#1924967).

* Sun Jan 17 2021 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-9
- Rebuild against kernel-4.18.0-275.el8.

* Mon Jan 04 2021 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-8
- Check for symvers.gz presence in /lib/modules/KVER in addition to boot
  (#1912195).

* Tue Dec 29 2020 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-7
- Rebuild against kernel-4.18.0-268.el8.

* Wed Dec 23 2020 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-6
- Rebuild against kernel-4.18.0-256.el8.

* Fri Nov 27 2020 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-5
- Rebuild against kernel-4.18.0-254.el8.

* Sat Nov 21 2020 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-4
- Rebuild against kernel-4.18.0-252.el8.

* Fri Oct 30 2020 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-3
- Add "Provides: oracleasm" and "Provides: oracleasm-kmod".
- Dropping "0001-oracleasm-driver-replace-fs_context-with-mount_pseud.patch".

* Thu Oct 22 2020 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-2
- Revision bump due to brew NVR conflict.

* Mon Oct 19 2020 Eugene Syromiatnikov <esyr@redhat.com> 2.0.8-1
- 19e841b848491d1e14dcd0063d8d681ed1190255
- oracleasm kernel module
- Resolves: #1827015

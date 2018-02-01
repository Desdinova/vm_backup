#!/usr/bin/env python3
#
# VM-Backup
# Version:	0.4
# tbd: logging, libvirt, change domain shutdown time
# Dependencies: python3-psutil
# Funktioniert und macht rolling snapshots, allerdings alle ACTIVE und auf der gleichen Maschine
#

# Import modules
import datetime, subprocess, re, time, os
# datetime: module for date
# subprocess: module for communation with operating system
# re: module to extract float or integer from string
# time: module to implement delay

# Set variables
# ==========================================================================================================
today = datetime.date.today() 		# today's date
kdnr = 'fn1000'				# Kundennummer
vm_name = 'fn1000-linux-test'
vm_conf = '/etc/xen/testserver.conf'
lvm_path = '/dev/vg1/testserver'
snap_size = 5
snap_count = 3
snap_path = '/snapshots/' + kdnr + '/' + vm_name + '/' + str(today)
# ==========================================================================================================


print('Date:			' + str(today))
print('VM:			' + vm_name)
print('Path:			' + lvm_path)
print('Snapshot Size:		' + str(snap_size) + 'GB')
print('Number of Snapshots:	' + str(snap_count))
print('Snap Path:		' + str(snap_path))


# Check if vm is running
# xl only uses stderr for successful and failed shutdown attempts!
# ==========================================================================================================
# "Is the vm running?"-Function
def vm_running_test(vm):							# Function checks if vm is listed by xl list vm_name
  xl_list_server = subprocess.Popen(['xl','list',vm], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  vm_run, vm_down = xl_list_server.communicate()		# if vm is running output comes from stdout, if not: stderr
  if 'invalid domain identifier' in str(vm_down) and vm in str(vm_down):		# if the string "invalid ..." and the vm_name appear in stderr ...
    # stdout is not used here
    return False
  else:
    # stderr is not used here
    return True
  
# Pause vm and dump RAM
if vm_running_test(vm_name) == True:
  os.makedirs(snap_path, exist_ok=True)						# create path und ignore if already exists
  xl_save = subprocess.Popen(['xl','save','-p',vm_name,snap_path + '/' + vm_name + '.ram'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)		# xl shutdown and pipe stdout and stderr
  shutdown_stdout, shutdown_stderr = xl_save.communicate()			# execute xl_shutdown and store the values of stdout and stderr
  print(shutdown_stdout)							# stdout not needed here. xl uses stderr for output
  print(shutdown_stderr)
elif vm_running_test(vm_name) == False:
  print('Server ' + vm_name + ' is not running. NO SNAPSHOT CREATED!')
  exit()
# ==========================================================================================================





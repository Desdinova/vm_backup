#!/usr/bin/env python3
#
# VM-Backup
# Version:	0.1
# tbd: logging, libvirt, change domain shutdown time
# Dependencies: python3-psutil
#

# Import modules
import datetime, subprocess, re, time
# datetime: module for date
# subprocess: module for communation with operating system
# re: module to extract float or integer from string
# time: module to implement delay

# Set variables
# ==========================================================================================================
today = datetime.date.today() 		# today's date
vm_name = 'testserver'
vm_conf = '/etc/xen/testserver.conf'
lvm_path = '/dev/vg1/testserver'
snap_size = 5
snap_count = 3
shutdown = True 			# for servers that need to be shut down for consistent snapshots set "True"
max_shutdown_time = 5			# time to wait for vm shutdown in minutes
# ==========================================================================================================


print('Date:			' + str(today))
print('VM:			' + vm_name)
print('Path:			' + lvm_path)
print('Snapshot Size:		' + str(snap_size) + 'GB')
print('Number of Snapshots:	' + str(snap_count))



# Checking disk space
# ==========================================================================================================
# Get available disk space and make it a float
diskspace_raw = subprocess.Popen(['pvs','-o','pv_free'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
diskspace_raw.stdout = diskspace_raw.communicate()			# get output from "pvs -o pv_free"
diskspace_raw_str = str(diskspace_raw.stdout)				# make stdout-tuple a string
diskspace_raw_period = diskspace_raw_str.replace(',','.')		# replace "," with "."
diskspace_clean = re.findall(r'\d+\.*\d*',diskspace_raw_period)		# extract Number; returns list
diskspace = float(diskspace_clean[0])					# make entry 0 in list a float
print(diskspace)

# Check if enough disk space left
if diskspace <= snap_size:
  print('Not enough disk space available')
  exit()  
# ==========================================================================================================



# Checking if vm is running and stopping the vm if needed
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
  
# Stopping the vm
if shutdown == True:
  if vm_running_test(vm_name) == True:
    xl_shutdown = subprocess.Popen(['xl','shutdown',vm_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)		# xl shutdown and pipe stdout and stderr
    shutdown_stdout, shutdown_stderr = xl_shutdown.communicate()		# execute xl_shutdown and store the values of stdout and stderr
  # print(shutdown_stdout)							# stdout not needed here. xl uses stderr for output
  # print(shutdown_stderr)
    if 'invalid domain identifier' in str(shutdown_stderr) and 'testserver' in str(shutdown_stderr):
      print('Domain is not running!')
      exit()
    else:									# while xl list testserver != "testserver is an invalid domain identifier (rc=-6)" do xl list testserver
      print('Domain is shutting down')
      time.sleep(5)								# wait 180 seconds for the vm to shut down
  else:
    print('Domain "' + vm_name + '" is not running!')
    exit()
elif vm_running_test(vm_name) == False:
  print('Server ' + vm_name + ' is not running. NO SNAPSHOT CREATED!')
  exit()
else:
  print('No shutdown required')
# ==========================================================================================================



# Creating the snapshot
# ==========================================================================================================
# Define "create snapshot"-Function
def make_snapshot(vm,path):			# vm = vm_name; path = lvm_path
  create_snapshot = subprocess.Popen(['lvcreate','-n',vm + '_snap_' + str(today),'-L',str(snap_size) + 'G','-s',path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  create_snapshot_stdout = create_snapshot.communicate()
  print(create_snapshot_stdout)

# Check if vm is shut down and create snapshot
if shutdown == True:
  if vm_running_test(vm_name) == False:
    make_snapshot(vm_name,lvm_path)
  else:
    counter = 0
    while counter <= max_shutdown_time:
      if counter == max_shutdown_time:
        print('Server '+ vm_name + ' did not shut down in ' + max_shutdown_time + ' minutes. NO SNAPSHOT CREATED! Please check the server.')
        exit()
      elif vm_running_test(vm_name) == True:
        print('Server ' + vm_name + ' is still running')
        counter += 1
        time.sleep(60)
      elif vm_running_test(vm_name) == False:
        make_snapshot(vm_name,lvm_path)
else:   
   make_snapshot(vm_name,lvm_path)   
# ==========================================================================================================



time.sleep(10)			# wait 10 seconds to be sure lvm creation is finished



# Starting the virtual machine
# ==========================================================================================================
if shutdown == True:
  xl_create = subprocess.Popen(['xl','create',vm_conf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  xl_create_stdout, xl_create_stderr = xl_create.communicate()
  print(xl_create_stdout)
  print(xl_create_stderr)
# ==========================================================================================================



# Deleting old snapshots
# ==========================================================================================================
# Define Function to return a list of dates
# Get existing snapshots and clean up output
def list_snap_dates(srv):			# srv = vm_name
  get_lvs = subprocess.Popen(['lvscan'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  get_lvs_stdout, get_lvs_stderr = get_lvs.communicate()
  get_lvs_utf8 = get_lvs_stdout.decode('utf-8')							# convert bytes to utf-8
  get_lvs_utf8_list = get_lvs_utf8.split()							# make a list
  snap_list = [x for x in get_lvs_utf8_list if srv + '_snap' in x]				# filter elements with testerserver_snap
  snap_date_clean = [s.replace("/dev/vg1/testserver_snap_",'') for s in snap_list]		# extract the date
  snap_date_only = [n.replace("\'",'') for n in snap_date_clean]				# delete '
  snap_date_only_sorted = sorted(snap_date_only, key=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'))	# a list with only dates sorted by date
  return snap_date_only_sorted

# Delete snapshots if rolling snapshot depth is exceeded
if len(list_snap_dates(vm_name)) > snap_count:
  while len(list_snap_dates(vm_name)) > snap_count:
    delete_snap = subprocess.Popen(['lvremove','-f',lvm_path + '_snap_' + list_snap_dates(vm_name)[0]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print('lvremove','-f',lvm_path + '_snap_' + list_snap_dates(vm_name)[0])
    delete_snap_stdout, delete_snap_stderr = delete_snap.communicate()
    print(delete_snap_stdout)
    print(delete_snap_stderr)




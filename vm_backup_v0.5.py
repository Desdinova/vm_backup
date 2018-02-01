#!/usr/bin/env python3
#
# VM-Backup
# Version:	0.5
# tbd: libvirt
# Dependencies: python3-psutil
# Rolling snapshots: LVM-snapshot without pausing the vm; dd into image file; Linux only

# USAGE:
# Create the snapshot LVM for the costumer and mount it to /var/lib/xen/<KDNR>
# Edit the variables in the set variables section.
# Rename the script to NAME_OF_VM.py and make it executeable with chmod +x
# Copy the script to /usr/local/bin and add it to crontab with crontab -e

# Set variables
# ==========================================================================================================
kdnr = 'fn1000'					# Kundennummer
vm_name = 'fn1000-linux-test'			# name of the virtual machine
vm_conf = '/etc/xen/fn1000-linux-test.conf'	# location of the vms config file
lvm_path = '/dev/vg1/fn1000-linux-test'		# lvm path of the vm (no trailing /)
snap_size = 5					# size of the intermediate snapshot
img_count = 3					# number of images; snapshot depth
debug = True					# show debug messages on manual execution (True/False)
# ==========================================================================================================






# Import modules: do not touch
import datetime, subprocess, re, time, os, atexit, smtplib, socket, logging, logging.handlers
# datetime: module for date
# subprocess: module for communation with operating system
# re: module to extract float or integer from string
# time: module to implement delay
# os: module basic oparating system functions like making dirs etc.
# atexit: module to execute functions on exit
# smtplib: module for SMTP
# socket: module to get hostname
# logging: module for logging to syslog


# Generated variables; do not edit
# ==========================================================================================================
today = datetime.date.today() 				# today's date
snap_name = vm_name + '_snap'				# name of the lvm snapshot
img_name = vm_name + "_" + str(today) + ".img"		# name of the image file
img_path = '/var/lib/xen/' + kdnr + '/' + vm_name	# path for the final image
pid = str(os.getpid())					# process ID of this script
scriptname = os.path.basename(__file__)			# filename of this script
pidfile = "/var/run/" + scriptname + ".pid"		# full path to the pid file
hostname = socket.gethostname()				# linux hostname
dd = "/bin/dd"						# path to dd
lvremove = "/sbin/lvremove"				# path to lvremove
lvcreate = "/sbin/lvcreate"				# path to lvcreate
xl = "/usr/sbin/xl"
# ==========================================================================================================

# for debugging
if debug == True:
  print('Date:			' + str(today))
  print('VM:			' + vm_name)
  print('Path:			' + lvm_path)
  print('Snapshot Size:		' + str(snap_size) + 'GB')
  print('Number of Snapshots:	' + str(img_count))
  print('Snapshot Name:		' + snap_name)
  print('PID:			' + pid)
  print('Script name:		' + scriptname)
  print('PID file:		' + pidfile)
  print('Hostname:		' + hostname)



# Enable logging to syslog
# ==========================================================================================================
syslogger = logging.getLogger('MyLogger')
syslogger.setLevel(logging.INFO)					# at which severity level are the messages logged
handler = logging.handlers.SysLogHandler(address = '/dev/log')		# communication with linux's /dev/log
syslogger.addHandler(handler)

syslogger.info(scriptname + "[" + pid + "]: snapshot script started")


# Function: sending mails
# ==========================================================================================================
def send_mail(why):					# why = reason for sending the mail
  smtp_server = "mail2.infra.net"
  sender = hostname + "@infra.net"
  to = ["noc@infra.net"]
  subject = "Fehler bei Backup von " + vm_name + " auf " + hostname
  message = """\
From: %s
To: %s
Subject: %s

%s
  """ % (sender, ", ".join(to), subject, why)
  server = smtplib.SMTP(smtp_server)
  server.sendmail(sender, to, message)
  server.quit()


# Check if script is already running by looking for the pid file
# ==========================================================================================================
if os.path.isfile(pidfile):			# if the pid file already exists exit
  send_mail("Das Skript wird bereits ausgefuehrt. Kein Snapshot erzeugt!")
  syslogger.error(scriptname + "[" + pid + "]: Das Skript wird bereits ausgefuehrt. Kein Snapshot erzeugt!")
  exit()
else:						# if the pid doesn't exist, create it
  with open(pidfile, 'w') as f:
    f.write(pid)


# From here on every exit(), planned or not, will delete the pid file
# ==========================================================================================================
def remove_pidfile(file):			# file = pidfile : function to delete the pid file
  os.remove(file)

atexit.register(remove_pidfile, pidfile)	# if the script exits, call remove_pidfile



# check if image base path exists (/var/lib/xen/<kdnr>)
# ==========================================================================================================
if os.path.isdir('/var/lib/xen/' + kdnr) == False:
  send_mail("Der Snapshot-Basisordner des Kunden existiert nicht. Es wurde kein Snapshot erzeugt!")
  syslogger.error(scriptname + "[" + pid + "]: Der Basisordner für Snapshots /var/lib/xen/" + kdnr + " existiert nicht. Es wurde kein Snapshot erzeugt!")
  exit()



# Function: check if vm is running
# xl only uses stderr for successful and failed shutdown attempts!
# ==========================================================================================================
def vm_running_test(vm):								# Function checks if vm is listed by xl list vm_name
  xl_list_server = subprocess.Popen([xl,'list',vm], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  vm_run, vm_down = xl_list_server.communicate()					# if vm is running output comes from stdout, if not: stderr
  if 'invalid domain identifier' in str(vm_down) and vm in str(vm_down):		# if the string "invalid ..." and the vm_name appear in stderr ...
    # stdout is not used here
    return False
  else:
    # stderr is not used here
    return True  



# Deleting old images
# ==========================================================================================================
# Function: return a list of dates from files in snapshot directory
# Get existing image files and clean up output
def list_img_dates(pth,vm):					# pth = img_path; vm=vm_name
  from os import walk						# walk gets folder and file lists
  files = []							# empty list to store files
  for (dirpath, dirnames, filenames) in walk(pth):		# all three needed (dirpath, dirnames, filenames)
    files.extend(filenames)
  img_date_noname = [s.replace(vm + "_",'') for s in files]					# remove vm name
  img_date_noimg = [s.replace(".img",'') for s in img_date_noname]				# remove .img
  img_date_sorted = sorted(img_date_noimg, key=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'))		# sort the dates
  return img_date_sorted

# Delete images if depth is exceeded
if len(list_img_dates(img_path,vm_name)) >= img_count:
  while len(list_img_dates(img_path,vm_name)) >= img_count:				# delete one image more, to free file space
    syslogger.info(scriptname + ": snapshot " +  vm_name + '_' + list_img_dates(img_path,vm_name)[0] + ".img deleted")		# syslog info
    os.remove(img_path + '/' +  vm_name + '_' + list_img_dates(img_path,vm_name)[0] + '.img')					# remove the snapshot
    


# Creating the snapshot
# ==========================================================================================================
# Function: create snapshot
def make_snapshot(snap,path):			# snap = snap_name; path = lvm_path
  create_snapshot = subprocess.Popen([lvcreate,'-n',snap,'-L',str(snap_size) + 'G','-s',path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  create_snapshot_stdout = create_snapshot.communicate()
  print(create_snapshot_stdout)

# Check if vm is running and create snapshot
if vm_running_test(vm_name) == True:
  make_snapshot(snap_name,lvm_path)
else:   
  send_mail('VM ist nicht gestartet. Kein snapshot erzeugt!')
  syslogger.error(scriptname + ": " + vm_name + " ist nicht gestartet. Kein snapshot erzeugt!")
  exit()   



# Creating an image from LVM snapshot; dd uses stderr for output
# ==========================================================================================================
os.makedirs(img_path, exist_ok=True)		# create the folder for the image; if it exists show no error
snap_to_image = subprocess.Popen([dd,'if=/dev/vg1/' + snap_name,'of=' + img_path + '/' + img_name,'bs=40M'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
snap_to_image_stdout, snap_to_image_stderr = snap_to_image.communicate()
syslogger.info(scriptname + "[" + pid + "]: image " + img_name + " created successfully")			# write to syslog



# Deleting the snapshot
# ==========================================================================================================
# Define "delete snapshot"-Function
def del_snapshot(snap):			# snap = snap_name
  remove_snapshot = subprocess.Popen([lvremove,'-f','/dev/vg1/' + snap], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  remove_snapshot_stdout = remove_snapshot.communicate()
  print(remove_snapshot_stdout)

# Remove snapshot
del_snapshot(snap_name)


syslogger.info( scriptname + "[" + pid + "]: snapshot script finished")
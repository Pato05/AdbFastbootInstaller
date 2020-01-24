from tkinter import Toplevel, FLAT, BOTH, X, IntVar, StringVar, HORIZONTAL, Text, END, Tk, LEFT, RIGHT
from tkinter.ttk import Label, Frame, Style, Button, Checkbutton, Progressbar, Entry
from tkinter.scrolledtext import ScrolledText
import tkinter.messagebox as messagebox
import os
import sys
import threading
from shutil import copyfile, rmtree
import winreg
from time import sleep
from tempfile import mkdtemp

installpaths = {}
imgdir = ''
scriptdir = ''

root = None

# Windows Registry Management functions


def getPath(system=False):
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE if system else winreg.HKEY_CURRENT_USER,
                         r'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment' if system else r'Environment', 0)
    return winreg.QueryValueEx(key, 'Path')[0]


def setPath(value, system=False):
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE if system else winreg.HKEY_CURRENT_USER,
                             r'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment' if system else r'Environment', 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, 'Path', 0, winreg.REG_SZ, value)
        return True
    except WindowsError as err:
        print('registry error')
        print('WINDOWSERROR: {}'.format(err))
        return False


def addToPath(add, system=False):
    path = getPath(system=system)
    add = str(add) + ';'
    o = False
    if system:
        if(path.find(add) < 0):
            o = setPath(add+path, True)
    else:
        if(path.find(add) < 0):
            o = setPath(add+path, False)
    return o


def clearPath(dir, system=False):
    path = getPath(system=system)
    dir = dir+';'
    modified = False
    if system:
        if path.find(dir) >= 0:
            path = path.replace(dir, '')
            setPath(path, True)
            modified = True
    else:
        if path.find(dir) >= 0:
            path = path.replace(dir, '')
            setPath(path, False)
            modified = True
    return modified

class MainWindow:
    def __init__(self):
        global root
        self.master = Toplevel(root)
        self.master.withdraw()
        self.master.protocol('WM_DELETE_WINDOW', root.destroy)
        self.master.iconbitmap(imgdir)
        self.master.geometry("400x150")
        self.master.resizable(False, False)
        self.master.title("Adb & Fastboot Installer - By @Pato05")
        estyle = Style()
        estyle.element_create("plain.field", "from", "clam")
        estyle.layout("White.TEntry",
                      [('Entry.plain.field', {'children': [(
                          'Entry.background', {'children': [(
                              'Entry.padding', {'children': [(
                                  'Entry.textarea', {'sticky': 'nswe'})],
                                  'sticky': 'nswe'})], 'sticky': 'nswe'})],
                          'border': '4', 'sticky': 'nswe'})])
        estyle.configure("White.TEntry",
                         background="white",
                         foreground="black",
                         fieldbackground="white")
        window = Frame(self.master, relief=FLAT)
        window.pack(padx=10, pady=5, fill=BOTH)
        Label(window, text='Installation path:').pack(fill=X)
        self.syswide = IntVar()
        self.instpath = StringVar()
        self.e = Entry(window, state='readonly',
                       textvariable=self.instpath, style='White.TEntry')
        self.e.pack(fill=X)
        self.toggleroot()
        Label(window, text='Options:').pack(pady=(10, 0), fill=X)
        inst = Checkbutton(window, text="Install Adb and Fastboot system-wide?",
                           variable=self.syswide, command=self.toggleroot)
        inst.pack(fill=X)
        self.path = IntVar(window, value=1)
        Checkbutton(window, text="Put Adb and Fastboot in PATH?",
                    variable=self.path).pack(fill=X)
        Button(window, text='Install', command=self.install).pack(anchor='se')
        self.master.deiconify()

    def toggleroot(self):
        if self.syswide.get() == 0:
            self.instpath.set(installpaths['user'])
        elif self.syswide.get() == 1:
            self.instpath.set(installpaths['system'])

    def install(self):
        self.app = InstallWindow(setpath=self.path.get(
        ), installpath=self.instpath.get(), systemwide=self.syswide.get())
        self.master.destroy()


class InstallWindow:
    def __init__(self, setpath, installpath, systemwide, type='install'):
        global root
        self.setpath = setpath
        self.installpath = installpath
        self.systemwide = systemwide

        self.type = type

        self.master = Toplevel(root)
        self.master.withdraw()
        self.master.protocol('WM_DELETE_WINDOW', self.close)
        self.master.iconbitmap(imgdir)
        self.master.title('Adb & Fastboot installer - By @Pato05')
        self.master.geometry("600x400")
        self.master.resizable(False, False)
        frame = Frame(self.master, relief=FLAT)
        frame.pack(padx=10, pady=5, fill=BOTH)
        Label(frame, text='Please wait while Adb and Fastboot are getting %s...' % (
            'updated' if type == 'update' else 'installed on your PC')).pack(fill=X)
        self.mode = 'unksize'
        self.progressbar = Progressbar(
            frame, orient=HORIZONTAL, length=100, mode='indeterminate')
        self.progressbar.pack(fill=X)
        self.progressbar.start(20)
        self.downloaded = 0
        self.progressv = Text(frame, bd=0, insertborderwidth=0,
                              state='disabled', background='#f0f0ed', font=('Segoe UI', 10))
        self.progressv.pack(fill=BOTH, pady=(10, 5))
        self.master.deiconify()
        self.downloading = threading.Thread(target=self.download)
        self.downloading.start()

    def download_progress(self, count, block_size, total_size):
        if total_size != -1 and self.mode != 'ksize':
            self.mode = 'ksize'
            self.progressbar.stop()
            self.progressbar.configure(mode='determinate', maximum=total_size)
        elif total_size == -1 and self.mode != 'unksize':
            self.mode = 'unksize'
            self.progressbar.configure(mode='indeterminate')
        if self.mode == 'ksize':
            self.downloaded += block_size
            self.progressbar.step(block_size)
            if self.downloaded == total_size:
                self.progress('Download ended.')

    def download(self):
        self.pathres = False
        self.progress('Downloading Adb and Fastboot...', False)
        from urllib.request import urlretrieve
        import urllib.error
        workingdir = scriptdir
        download = os.path.join(workingdir, 'pt.zip')
        try:
            urlretrieve('https://dl.google.com/android/repository/platform-tools-latest-windows.zip',
                        download, self.download_progress)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            messagebox.showerror(title='Adb & Fastboot Uninstaller',
                                 message='Failed while trying to download Adb and Fastboot. Are you connected to the internet?\nError: %s' % e)
            self.error_close()
            return False
        self.progressbar.configure(
            mode='indeterminate', maximum=150, length=400, value=0)
        self.progressbar.start(20)
        self.progress('Extracting Adb and Fastboot...')
        from zipfile import ZipFile
        with ZipFile(download) as z:
            z.extractall(workingdir)
        os.remove(download)
        self.progress('Moving Adb and Fastboot to destination folder...')
        if(os.path.isdir(self.installpath)):
            rmtree(self.installpath)
            sleep(0.1)
        os.mkdir(self.installpath)
        for file in ['adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'fastboot.exe']:
            self.progress("Moving %s..." % file)
            copyfile(os.path.join(workingdir, 'platform-tools', file), os.path.join(self.installpath, file))
        rmtree(os.path.join(workingdir, 'platform-tools'))
        if self.setpath == 1:
            self.progress('Adding Adb & Fastboot into %s\'s path' %
                          ('system' if self.systemwide == 1 else 'user'))
            self.pathres = addToPath(self.installpath, self.systemwide == 1)
            self.progress(
                'Successfully added Adb & Fastboot into path' if self.pathres else 'Failed to add Adb & Fastboot into path')
        self.progressbar.stop()
        self.finish()

    def finish(self):
        self.app = FinishWindow(
            self.setpath, self.pathres, self.installpath, self.type)
        self.master.destroy()

    def progress(self, what, lb=True):
        self.progressv.configure(state='normal')
        self.progressv.insert(END, ('\r\n' if lb else '')+what)
        self.progressv.configure(state='disabled')

    def error_close(self):
        global root
        root.destroy()

    def close(self):
        pass


class FinishWindow:
    def __init__(self, setpath, pathres, installpath, type='install'):
        global root
        self.master = Toplevel(root)
        self.master.withdraw()
        self.master.protocol('WM_DELETE_WINDOW', root.destroy)
        self.master.iconbitmap(imgdir)
        self.master.title('Adb & Fastboot installer - By @Pato05')
        self.master.resizable(False, False)
        frame = Frame(self.master, relief=FLAT)
        frame.pack(padx=10, pady=5, fill=BOTH)
        Label(frame, text=('Adb & Fastboot were successfully %s!' % (
            'updated' if type == 'update' else type+'ed')), font=('Segoe UI', 15)).pack(fill=X)
        if installpath is not None:
            Label(frame, text='Installation path: %s' %
                  installpath, font=('Segoe UI', 12)).pack(fill=X)
        if setpath == 1 and pathres:
            Label(frame, text='You might need to restart applications to update PATH.', font=(
                'Segoe UI', 12)).pack(fill=X)
        elif setpath == 1 and not pathres:
            Style().configure('Red.TLabel', foreground='red')
            Label(frame, text='Failed to put Adb & Fastboot into path.',
                  font=('Segoe UI', 12), style='Red.TLabel').pack(fill=X)
        self.master.deiconify()


class UninstallWindow:
    def __init__(self, installpath, installtype):
        global root
        self.installpath = installpath
        self.installtype = installtype
        self.master = Toplevel(root)
        self.master.withdraw()
        self.master.iconbitmap(imgdir)
        self.master.protocol('WM_DELETE_WINDOW', root.destroy)
        self.master.title('Adb & Fastboot uninstaller - By @Pato05')
        self.master.resizable(False, False)
        self.master.geometry('400x100+100+100')
        frame = Frame(self.master, relief=FLAT)
        frame.pack(padx=10, pady=5, fill=BOTH)
        Label(frame, text='Found an installation of Adb & Fastboot.',
              font=('Segoe UI', 12)).pack(fill=X)
        Label(frame, text='What do you want to do?',
              font=('Segoe UI', 12)).pack(fill=X)
        btnframe = Frame(frame, relief=FLAT)
        btnframe.pack(fill=X, pady=(10, 0))
        Button(btnframe, text='Uninstall', command=self.uninstall).pack(
            side=LEFT, anchor='w', expand=1)
        Button(btnframe, text='Update', command=self.update).pack(
            side=RIGHT, anchor='e', expand=1)
        self.master.deiconify()

    def uninstall(self):
        self.app = FinishWindow(True, self.remove(True), None, 'uninstall')
        self.master.destroy()

    def remove(self, removePath=True):
        from subprocess import call as subcall
        subcall([os.path.join(self.installpath, "adb.exe"), 'kill-server'], creationflags=0x00000008)
        rmtree(self.installpath)
        if removePath:
            return clearPath(self.installpath, self.installtype == 'system')
        else:
            return True

    def update(self):
        self.remove(False)
        self.app = InstallWindow(
            False, self.installpath, self.installtype == 'system', 'update')
        self.master.destroy()


if __name__ == "__main__":
    installpaths = {'system': '%s\\adbfastboot'%os.getenv('systemdrive'), 'user': os.path.join(os.getenv('localappdata'), 'adbfastboot')}
    scriptdir = sys.prefix if hasattr(
        sys, 'frozen') else os.path.dirname(__file__)
    imgdir = os.path.join(scriptdir, 'res\\icon.ico')
    root = Tk()
    root.withdraw()
    instfound = ''
    insttype = ''
    for i in installpaths:
        if(os.path.isdir(installpaths[i])):
            instfound = installpaths[i]
            insttype = i
    app = (MainWindow() if instfound ==
           '' else UninstallWindow(instfound, insttype))
    root.mainloop()
    print('rip mainloop')

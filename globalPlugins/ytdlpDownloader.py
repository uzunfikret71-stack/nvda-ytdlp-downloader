# -*- coding: UTF-8 -*-
# ytdlpDownloader: NVDA add-on for downloading video and audio with yt-dlp.
# Copyright (C) 2026 Fikret Uzun
# Licensed under the GNU General Public License version 2 or later.

import os
import json
import subprocess
import threading
import time
import urllib.request
import re

import addonHandler
import config
import globalPluginHandler
import gui
import scriptHandler
import wx
from logHandler import log


addonHandler.initTranslation()

ADDON_DIR = os.path.dirname(os.path.dirname(__file__))
BIN_DIR = os.path.join(ADDON_DIR, "bin")
YTDLP_EXE = os.path.join(BIN_DIR, "yt-dlp.exe")
FFMPEG_EXE = os.path.join(BIN_DIR, "ffmpeg.exe")
FFPROBE_EXE = os.path.join(BIN_DIR, "ffprobe.exe")
DENO_EXE = os.path.join(BIN_DIR, "deno.exe")
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
PROCESS_FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
CONFIG_SECTION = "ytdlpDownloader"
UPDATE_CHECK_INTERVAL = 24 * 60 * 60
YTDLP_RELEASE_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"


def registerConfigSpec():
	"""Register persistent settings with NVDA's configuration manager."""
	config.conf.spec[CONFIG_SECTION] = {
		"outputDirectory": "string(default='')",
		"lastUpdateCheck": "integer(default=0)",
	}


def getSavedOutputDirectory():
	try:
		return config.conf[CONFIG_SECTION]["outputDirectory"]
	except (KeyError, TypeError):
		return ""


def saveOutputDirectory(path):
	config.conf[CONFIG_SECTION]["outputDirectory"] = path


class DownloadDialog(wx.Dialog):
	def __init__(self, parent, onDestroyed=None):
		super().__init__(parent, title=_("Video ve Ses İndirici"), size=(660, 520))
		self.process = None
		self.worker = None
		self.closed = False
		self.lastProgress = -1
		self._onDestroyed = onDestroyed

		panel = wx.Panel(self)
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		mainSizer.Add(wx.StaticText(panel, label=_("Video veya oynatma listesi adresi:")), 0, wx.ALL, 8)
		self.urlCtrl = wx.TextCtrl(panel)
		mainSizer.Add(self.urlCtrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		typeBox = wx.StaticBoxSizer(wx.StaticBox(panel, label=_("İndirme türü")), wx.VERTICAL)
		self.videoRadio = wx.RadioButton(panel, label=_("Video olarak indir"), style=wx.RB_GROUP)
		self.audioRadio = wx.RadioButton(panel, label=_("Ses olarak indir"))
		typeBox.Add(self.videoRadio, 0, wx.ALL, 6)
		typeBox.Add(self.audioRadio, 0, wx.ALL, 6)
		mainSizer.Add(typeBox, 0, wx.EXPAND | wx.ALL, 8)

		formatSizer = wx.FlexGridSizer(2, 2, 8, 8)
		formatSizer.AddGrowableCol(1, 1)
		formatSizer.Add(wx.StaticText(panel, label=_("Video biçimi:")), 0, wx.ALIGN_CENTER_VERTICAL)
		self.videoFormat = wx.Choice(
			panel,
			choices=[
				_("En iyi video (mp4 tercih et)"),
				_("En iyi video (orijinal)"),
				"mp4",
				"mkv",
				"webm",
			],
		)
		self.videoFormat.SetSelection(0)
		formatSizer.Add(self.videoFormat, 1, wx.EXPAND)
		formatSizer.Add(wx.StaticText(panel, label=_("Ses biçimi:")), 0, wx.ALIGN_CENTER_VERTICAL)
		self.audioFormat = wx.Choice(
			panel,
			choices=[
				_("En iyi ses (webm hariç)"),
				_("En iyi ses (orijinal)"),
				"mp3",
				"m4a",
				"flac",
				"wav",
			],
		)
		self.audioFormat.SetSelection(0)
		formatSizer.Add(self.audioFormat, 1, wx.EXPAND)
		mainSizer.Add(formatSizer, 0, wx.EXPAND | wx.ALL, 8)

		self.audioOptionsBox = wx.StaticBoxSizer(
			wx.StaticBox(panel, label=_("Ses dosyası seçenekleri")), wx.VERTICAL
		)
		self.metadataCheck = wx.CheckBox(
			panel, label=_("Başlık, sanatçı ve benzeri medya bilgilerini dosyaya ekle")
		)
		self.thumbnailCheck = wx.CheckBox(
			panel, label=_("Video küçük resmini ses dosyasına kapak görseli olarak ekle")
		)
		self.audioOptionsBox.Add(self.metadataCheck, 0, wx.ALL, 6)
		self.audioOptionsBox.Add(self.thumbnailCheck, 0, wx.ALL, 6)
		mainSizer.Add(self.audioOptionsBox, 0, wx.EXPAND | wx.ALL, 8)

		pathSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.outputCtrl = wx.TextCtrl(panel, value=getSavedOutputDirectory())
		self.browseButton = wx.Button(panel, label=_("Klasör seç..."))
		pathSizer.Add(self.outputCtrl, 1, wx.EXPAND | wx.RIGHT, 8)
		pathSizer.Add(self.browseButton, 0)
		mainSizer.Add(wx.StaticText(panel, label=_("İndirilecek klasör:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		mainSizer.Add(pathSizer, 0, wx.EXPAND | wx.ALL, 8)

		statusBox = wx.StaticBoxSizer(wx.StaticBox(panel, label=_("İşlem durumu")), wx.VERTICAL)
		self.statusLabel = wx.StaticText(panel, label=_("Hazır"))
		self.progressGauge = wx.Gauge(panel, range=100)
		self.detailLabel = wx.StaticText(panel, label="")
		statusBox.Add(self.statusLabel, 0, wx.EXPAND | wx.ALL, 6)
		statusBox.Add(self.progressGauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
		statusBox.Add(self.detailLabel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
		mainSizer.Add(statusBox, 1, wx.EXPAND | wx.ALL, 8)

		buttonSizer = wx.StdDialogButtonSizer()
		self.startButton = wx.Button(panel, wx.ID_OK, label=_("İndirmeyi başlat"))
		self.updateButton = wx.Button(panel, label=_("yt-dlp güncelle"))
		self.closeButton = wx.Button(panel, wx.ID_CANCEL, label=_("Kapat"))
		buttonSizer.AddButton(self.startButton)
		buttonSizer.AddButton(self.closeButton)
		buttonSizer.Realize()
		buttonRow = wx.BoxSizer(wx.HORIZONTAL)
		buttonRow.Add(self.updateButton, 0, wx.RIGHT, 8)
		buttonRow.AddStretchSpacer()
		buttonRow.Add(buttonSizer, 0)
		mainSizer.Add(buttonRow, 0, wx.EXPAND | wx.ALL, 8)

		panel.SetSizer(mainSizer)
		self.Bind(wx.EVT_RADIOBUTTON, self.onTypeChanged, self.videoRadio)
		self.Bind(wx.EVT_RADIOBUTTON, self.onTypeChanged, self.audioRadio)
		self.Bind(wx.EVT_CHOICE, self.onAudioFormatChanged, self.audioFormat)
		self.Bind(wx.EVT_BUTTON, self.onBrowse, self.browseButton)
		self.Bind(wx.EVT_BUTTON, self.startUpdater, self.updateButton)
		self.Bind(wx.EVT_BUTTON, self.onStart, self.startButton)
		self.Bind(wx.EVT_BUTTON, self.onClose, self.closeButton)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.onTypeChanged(None)
		wx.CallAfter(self.startAutomaticUpdateCheck)

	def onTypeChanged(self, event):
		isAudio = self.audioRadio.GetValue()
		self.audioFormat.Enable(isAudio)
		self.videoFormat.Enable(not isAudio)
		self.updateAudioOptions()

	def onAudioFormatChanged(self, event):
		self.updateAudioOptions()

	def updateAudioOptions(self):
		isSupported = self.audioRadio.GetValue() and self.audioFormat.GetSelection() in (0, 2, 3, 4)
		for option in (self.metadataCheck, self.thumbnailCheck):
			if not isSupported:
				option.SetValue(False)
			option.Enable(isSupported)

	def onBrowse(self, event):
		currentPath = self.outputCtrl.GetValue().strip()
		dialogArgs = {
			"message": _("İndirilecek klasörü seç"),
			"style": wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
		}
		if os.path.isdir(currentPath):
			dialogArgs["defaultPath"] = currentPath
		with wx.DirDialog(self, **dialogArgs) as dialog:
			if dialog.ShowModal() == wx.ID_OK:
				selectedPath = dialog.GetPath()
				self.outputCtrl.SetValue(selectedPath)
				saveOutputDirectory(selectedPath)

	def setBusy(self, busy):
		if self.closed:
			return
		self.startButton.Enable(not busy)
		self.updateButton.Enable(not busy)
		self.browseButton.Enable(not busy)
		self.urlCtrl.Enable(not busy)
		self.outputCtrl.Enable(not busy)
		self.videoRadio.Enable(not busy)
		self.audioRadio.Enable(not busy)
		self.videoFormat.Enable(not busy)
		self.audioFormat.Enable(not busy)
		self.metadataCheck.Enable(not busy)
		self.thumbnailCheck.Enable(not busy)
		if not busy:
			self.onTypeChanged(None)

	def buildProcessEnv(self):
		env = os.environ.copy()
		env["PATH"] = BIN_DIR + os.pathsep + env.get("PATH", "")
		return env

	def startUpdater(self, event=None):
		if self.isWorkerActive():
			wx.MessageBox(_("Başka bir işlem devam ediyor."), _("İşlem sürüyor"), wx.OK | wx.ICON_WARNING, self)
			return
		if not os.path.isfile(YTDLP_EXE):
			self.setStatus(_("yt-dlp.exe bulunamadı."))
			return
		answer = wx.MessageBox(
			_("yt-dlp güncellenecek ve bu işlem internet bağlantısı kullanacaktır. Devam etmek istiyor musunuz?"),
			_("yt-dlp güncelle"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
			self,
		)
		if answer != wx.YES:
			return
		self.runUpdater()

	def runUpdater(self):
		self.setBusy(True)
		self.setStatus(_("yt-dlp güncelleniyor..."), pulse=True)
		self.worker = threading.Thread(target=self.runProcess, args=([YTDLP_EXE, "-U"], True), daemon=True)
		self.worker.start()

	def setStatus(self, text, percent=None, detail="", pulse=False):
		if self.closed:
			return
		self.statusLabel.SetLabel(text)
		self.detailLabel.SetLabel(detail)
		if pulse:
			self.progressGauge.Pulse()
		elif percent is not None:
			self.progressGauge.SetValue(max(0, min(100, int(percent))))
		self.Layout()

	def startAutomaticUpdateCheck(self):
		if self.closed or not os.path.isfile(YTDLP_EXE):
			return
		try:
			lastCheck = int(config.conf[CONFIG_SECTION]["lastUpdateCheck"])
		except (KeyError, TypeError, ValueError):
			lastCheck = 0
		if time.time() - lastCheck < UPDATE_CHECK_INTERVAL:
			return
		threading.Thread(target=self.checkLatestVersion, daemon=True).start()

	def checkLatestVersion(self):
		try:
			versionResult = subprocess.run(
				[YTDLP_EXE, "--version"], capture_output=True, text=True,
				encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW, timeout=5,
			)
			current = versionResult.stdout.strip().splitlines()[0]
			request = urllib.request.Request(
				YTDLP_RELEASE_API,
				headers={"Accept": "application/vnd.github+json", "User-Agent": "NVDA-ytdlpDownloader"},
			)
			with urllib.request.urlopen(request, timeout=8) as response:
				latest = json.loads(response.read().decode("utf-8")).get("tag_name", "").strip()
			wx.CallAfter(self.recordUpdateCheck)
			if latest and current and not self.closed:
				wx.CallAfter(self.handleUpdateCheck, latest, current)
		except (OSError, ValueError, TypeError, IndexError, subprocess.SubprocessError):
			# Ağ sorunu indirme işlevini engellememelidir.
			return

	def recordUpdateCheck(self):
		if not self.closed:
			config.conf[CONFIG_SECTION]["lastUpdateCheck"] = int(time.time())

	def handleUpdateCheck(self, latest, current):
		if self.closed or self.isWorkerActive():
			return
		versionParts = lambda value: tuple(int(part) for part in re.findall(r"\d+", value)[:4])
		if versionParts(latest) <= versionParts(current):
			self.setStatus(_("Hazır"), 0, _("yt-dlp güncel: %s") % current)
			return
		answer = wx.MessageBox(
			_("Yeni bir yt-dlp sürümü mevcut: %s (yüklü: %s). Şimdi güncellensin mi?") % (latest, current),
			_("yt-dlp güncellemesi mevcut"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION, self,
		)
		if answer == wx.YES and not self.isWorkerActive():
			self.runUpdater()

	def onStart(self, event):
		if self.isWorkerActive():
			return
		url = self.urlCtrl.GetValue().strip()
		outputDir = self.outputCtrl.GetValue().strip()
		if not url:
			wx.MessageBox(_("Lütfen indirilecek video veya oynatma listesi adresini yazın."), _("Eksik bilgi"), wx.OK | wx.ICON_WARNING, self)
			return
		if not outputDir:
			wx.MessageBox(_("Lütfen Klasör seç düğmesiyle hedef klasörü seçin."), _("Eksik bilgi"), wx.OK | wx.ICON_WARNING, self)
			return
		if not os.path.isdir(outputDir):
			wx.MessageBox(_("Seçilen hedef klasör bulunamadı."), _("Eksik bilgi"), wx.OK | wx.ICON_WARNING, self)
			return
		missing = [name for name, path in (("yt-dlp.exe", YTDLP_EXE), ("ffmpeg.exe", FFMPEG_EXE), ("ffprobe.exe", FFPROBE_EXE), ("deno.exe", DENO_EXE)) if not os.path.isfile(path)]
		if missing:
			wx.MessageBox(_("Eksik bağımlılık: %s") % ", ".join(missing), _("Eksik bağımlılık"), wx.OK | wx.ICON_ERROR, self)
			return

		saveOutputDirectory(outputDir)
		command = self.buildCommand(url, outputDir)
		self.setBusy(True)
		self.setStatus(_("İndirme başlatılıyor..."), 0)
		self.worker = threading.Thread(target=self.runProcess, args=(command, False), daemon=True)
		self.worker.start()

	def buildCommand(self, url, outputDir):
		command = [
			YTDLP_EXE,
			"--ffmpeg-location", BIN_DIR,
			"--newline",
			"--windows-filenames",
			"-P", outputDir,
			"-o", "%(playlist_index&{} - |)s%(title)s.%(ext)s",
		]
		if self.audioRadio.GetValue():
			audioSelection = self.audioFormat.GetSelection()
			if audioSelection == 1:
				command.extend(["-f", "ba"])
			elif audioSelection == 0:
				# Keep the source audio stream as-is: no WebM fallback and no
				# extraction/conversion postprocessor for this automatic choice.
				command.extend(["-f", "ba[ext!=webm]"])
			else:
				command.extend(["-f", "ba[ext!=webm]/ba", "-x"])
				command.extend(["--audio-format", self.audioFormat.GetStringSelection()])
			if audioSelection in (0, 2, 3, 4) and self.metadataCheck.GetValue():
				command.append("--add-metadata")
			if audioSelection in (0, 2, 3, 4) and self.thumbnailCheck.GetValue():
				command.append("--embed-thumbnail")
		else:
			videoSelection = self.videoFormat.GetSelection()
			if videoSelection == 1:
				command.extend(["-f", "bv*+ba/b"])
			elif videoSelection == 0:
				command.extend(["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "--merge-output-format", "mp4/mkv"])
			elif videoSelection == 2:
				command.extend(["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]", "--merge-output-format", "mp4"])
			elif videoSelection == 4:
				command.extend(["-f", "bv*[ext=webm]+ba[ext=webm]/b[ext=webm]", "--merge-output-format", "webm"])
			else:
				command.extend(["-f", "bv*+ba/b", "--merge-output-format", self.videoFormat.GetStringSelection()])
				command.extend(["--remux-video", self.videoFormat.GetStringSelection()])
		# End option parsing before the user-supplied URL. This prevents a value
		# beginning with a dash from being interpreted as a yt-dlp option.
		command.extend(["--", url])
		return command

	def runProcess(self, command, isUpdate):
		errorLines = []
		try:
			if self.closed:
				return
			self.process = subprocess.Popen(
				command,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				shell=False,
				text=True,
				encoding="utf-8",
				errors="replace",
				creationflags=PROCESS_FLAGS,
				env=self.buildProcessEnv(),
			)
			# The dialog may have been closed in the brief interval while Popen
			# was creating the process. Do not leave that process orphaned.
			if self.closed:
				self.terminateProcessTree()
				return
			for line in self.process.stdout:
				cleanLine = line.strip()
				if cleanLine:
					errorLines.append(cleanLine)
					errorLines = errorLines[-8:]
				if not isUpdate:
					self.handleProcessLine(cleanLine)
			returnCode = self.process.wait()
			if self.closed:
				return
			if returnCode == 0 and not isUpdate:
				wx.CallAfter(self.finishDownload)
			elif returnCode == 0:
				wx.CallAfter(self.setStatus, _("yt-dlp güncellemesi tamamlandı."), 100)
			else:
				message = _("Güncelleme tamamlanamadı.") if isUpdate else _("İndirme başarısız oldu.")
				wx.CallAfter(self.showProcessError, message, errorLines)
		except Exception as exc:
			if not self.closed:
				wx.CallAfter(self.showProcessError, _("İşlem başlatılamadı."), [str(exc)])
		finally:
			self.process = None
			if not self.closed:
				wx.CallAfter(self.setBusy, False)

	def handleProcessLine(self, line):
		"""Convert yt-dlp's console output into a small, accessible status model."""
		percentMatch = re.search(r"\[download\]\s+(\d+(?:[.,]\d+)?)%", line)
		if percentMatch:
			percent = int(float(percentMatch.group(1).replace(",", ".")))
			if percent != self.lastProgress:
				self.lastProgress = percent
				etaMatch = re.search(r"\bETA\s+([^\s]+)", line)
				detail = _("Kalan süre: %s") % etaMatch.group(1) if etaMatch else ""
				wx.CallAfter(self.setStatus, _("İndiriliyor: yüzde %d") % percent, percent, detail)
			return
		stages = (
			("[Merger]", _("Video ve ses birleştiriliyor...")),
			("[ExtractAudio]", _("Ses dönüştürülüyor...")),
			("[VideoConvertor]", _("Video dönüştürülüyor...")),
			("[Metadata]", _("Medya bilgileri ekleniyor...")),
			("[EmbedThumbnail]", _("Kapak görseli ekleniyor...")),
		)
		for marker, status in stages:
			if marker in line:
				wx.CallAfter(self.setStatus, status, None, "", True)
				return

	def showProcessError(self, message, outputLines):
		if self.closed:
			return
		# Ham konsol çıktısını göstermeden yaygın hataları anlaşılır hale getir.
		combined = " ".join(outputLines).lower()
		if "unsupported url" in combined:
			detail = _("Bu adres yt-dlp tarafından desteklenmiyor.")
		elif "video unavailable" in combined or "not available" in combined:
			detail = _("İçerik kullanılamıyor veya seçilen biçim bulunamadı.")
		elif "private video" in combined or "login" in combined or "sign in" in combined:
			detail = _("Bu içerik oturum açma veya erişim izni gerektiriyor.")
		elif "network" in combined or "timed out" in combined or "unable to download" in combined:
			detail = _("Ağ bağlantısı kurulamadı. İnternet bağlantınızı kontrol edin.")
		else:
			detail = _("Adresi, internet bağlantısını ve seçilen biçimi kontrol edin.")
		self.setStatus(message, 0, detail)
		wx.MessageBox(message + "\n\n" + detail, _("İşlem başarısız"), wx.OK | wx.ICON_ERROR, self)

	def finishDownload(self):
		if self.closed:
			return
		self.setStatus(_("İndirme tamamlandı."), 100)
		wx.MessageBox(_("İndirme tamamlandı."), _("Tamamlandı"), wx.OK | wx.ICON_INFORMATION, self)

	def isProcessRunning(self):
		return self.process is not None and self.process.poll() is None

	def isWorkerActive(self):
		return self.worker is not None and self.worker.is_alive()

	def terminateProcessTree(self):
		process = self.process
		if process is None or process.poll() is not None:
			return
		threading.Thread(target=self._stopProcess, args=(process,), daemon=True).start()

	@staticmethod
	def _stopProcess(process):
		try:
			result = subprocess.run(
				["taskkill", "/PID", str(process.pid), "/T", "/F"],
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
				creationflags=CREATE_NO_WINDOW,
				check=False,
				timeout=5,
			)
			if result.returncode != 0 and process.poll() is None:
				process.terminate()
		except (OSError, subprocess.SubprocessError):
			log.warning("ytdlpDownloader: process tree cleanup failed")
			try:
				if process.poll() is None:
					process.terminate()
			except OSError:
				log.warning("ytdlpDownloader: process termination failed")
		try:
			process.wait(timeout=5)
		except (OSError, subprocess.SubprocessError):
			log.warning("ytdlpDownloader: process cleanup did not complete")

	def closeDialog(self):
		if self.closed:
			return
		self.closed = True
		self.terminateProcessTree()
		callback = self._onDestroyed
		self._onDestroyed = None
		self.Destroy()
		if callback:
			callback(self)

	def onClose(self, event):
		if self.isWorkerActive():
			answer = wx.MessageBox(
				_("Bir işlem devam ediyor. İşlemi durdurup pencereyi kapatmak istiyor musunuz?"),
				_("İşlem sürüyor"),
				wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
				self,
			)
			if answer != wx.YES:
				return
		self.closeDialog()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Video ve Ses İndirici")

	def __init__(self):
		super().__init__()
		registerConfigSpec()
		self.menuItem = None
		self.dialog = None
		self._terminated = False
		wx.CallAfter(self.addMenuItem)

	def addMenuItem(self):
		if self._terminated:
			return
		toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
		self.menuItem = toolsMenu.Append(wx.ID_ANY, _("Video veya ses indir..."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onMenuItem, self.menuItem)

	def terminate(self):
		if self._terminated:
			return
		self._terminated = True
		if self.dialog and not self.dialog.closed:
			self.dialog.closeDialog()
		if self.menuItem:
			try:
				gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, handler=self.onMenuItem, source=self.menuItem)
				gui.mainFrame.sysTrayIcon.toolsMenu.DestroyItem(self.menuItem)
			except (RuntimeError, wx.PyDeadObjectError):
				pass
			self.menuItem = None
		super().terminate()

	def onMenuItem(self, event):
		self.showDialog()

	def onDialogDestroyed(self, dialog):
		if self.dialog is dialog:
			self.dialog = None

	def showDialog(self):
		if self.dialog and not self.dialog.closed:
			self.dialog.Raise()
			self.dialog.SetFocus()
			return
		self.dialog = DownloadDialog(gui.mainFrame, self.onDialogDestroyed)
		self.dialog.Show()

	@scriptHandler.script(
		description=_("Video ve Ses İndirici penceresini açar"),
		gesture="kb:NVDA+shift+y",
	)
	def script_openDownloader(self, gesture):
		wx.CallAfter(self.showDialog)

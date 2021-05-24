
import webbrowser
from threading import Thread

import pafy
import pyperclip
import wx
from dialogs.download_progress import DownloadProgress
from dialogs.search_dialog import SearchDialog
from dialogs.settings_dialog import SettingsDialog
from download_handler.downloader import downloadAction
from media_player.media_gui import MediaGui
from media_player.player import Player
from nvda_client.client import speak
from settings_handler import config_get
from youtube_browser.search_handler import Search
from utiles import direct_download


class YoutubeBrowser(wx.Frame):
	def __init__(self, parent):
		wx.Frame.__init__(self, parent=parent, title=parent.Title)
		self.Centre()
		self.SetSize(wx.DisplaySize())
		self.Maximize(True)
		self.panel = wx.Panel(self)
		lbl = wx.StaticText(self.panel, -1, _("نتائج البحث: "))
		self.searchResults = wx.ListBox(self.panel, -1)
		self.loadMoreButton = wx.Button(self.panel, -1, _("تحميل المزيد من النتائج"))
		self.loadMoreButton.Enabled = False
		self.loadMoreButton.Show(not config_get("autoload"))
		self.playButton = wx.Button(self.panel, -1, _("تشغيل (enter)"), name="controls")
		self.downloadButton = wx.Button(self.panel, -1, _("تنزيل"), name="controls")
		searchButton = wx.Button(self.panel, -1, _("بحث... (ctrl+f)"))
		backButton = wx.Button(self.panel, -1, _("العودة إلى النافذة الرئيسية"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		sizer1.Add(backButton, 1, wx.ALL)
		sizer1.Add(searchButton, 1, wx.ALL)
		sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		for control in self.panel.GetChildren():
			if control.Name == "controls":
				sizer2.Add(control, 1)
		sizer.Add(sizer1, 1, wx.EXPAND)
		sizer.Add(lbl, 1, wx.ALL)
		sizer.Add(self.searchResults, 1, wx.EXPAND)
		sizer.Add(self.loadMoreButton, 1)
		sizer.Add(sizer2, 1)
		self.panel.SetSizer(sizer)
		self.contextSetup()
		menuBar = wx.MenuBar()
		optionsMenu = wx.Menu()
		settingsItem = optionsMenu.Append(-1, _("الإعدادات...\talt+s"))
		hotKeys = wx.AcceleratorTable([
			(wx.ACCEL_ALT, ord("S"), settingsItem.GetId()),
			(wx.ACCEL_CTRL, ord("F"), searchButton.GetId()),
			(wx.ACCEL_CTRL, ord("D"), self.directDownloadId)
		])
		# hotkey table
		self.SetAcceleratorTable(hotKeys)
		menuBar.Append(optionsMenu, _("خيارات"))
		self.SetMenuBar(menuBar)
		self.Bind(wx.EVT_MENU, lambda event: SettingsDialog(self), settingsItem)
		self.loadMoreButton.Bind(wx.EVT_BUTTON, self.onLoadMore)
		self.playButton.Bind(wx.EVT_BUTTON, lambda event: self.playVideo())
		self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
		searchButton.Bind(wx.EVT_BUTTON, self.onSearch)
		backButton.Bind(wx.EVT_BUTTON, lambda event: self.backAction())
		self.searchResults.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		self.searchResults.Bind(wx.EVT_KEY_DOWN, self.onKeyDown)
		self.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self.playVideo(), self.searchResults)
		self.searchResults.Bind(wx.EVT_LISTBOX, self.onListBox)
		self.Bind(wx.EVT_SHOW, self.onShow)
		self.Bind(wx.EVT_CLOSE, lambda event: wx.Exit())
		if self.searchAction():
			self.Show()
			self.Parent.Hide()
		else:
			self.Destroy()

	def searchAction(self, value=""):
		dialog = SearchDialog(self, value=value)
		query = dialog.query
		filter = dialog.filter
		if query is None:
			self.togleControls()
			return
		try:
			self.search = Search(query, filter)
		except:
			wx.MessageBox(_("تعذر إجراء عملية البحث بسبب وجود خلل ما في الاتصال بالشبكة."), _("خطأ"), style=wx.ICON_ERROR)
			self.searchAction(query)
		titles = self.search.get_titles()
		self.searchResults.Set(titles)
		self.togleControls()
		try:
			self.searchResults.SetSelection(0)
		except:
			pass
		self.searchResults.SetFocus()
		self.togleDownload()
		self.toglePlay()
		return True

	def onSearch(self, event):
		if hasattr(self, "search"):
			self.searchAction(self.search.query)
		else:
			self.searchAction()

	def playVideo(self):
		number = self.searchResults.Selection
		if self.search.get_type(number) == "playlist":
			return
		title = self.search.get_title(number)
		url = self.search.get_url(number)
		speak(_("جاري التشغيل"))
		media = pafy.new(url)
		gui = MediaGui(self, title, url, True if self.search.get_views(number) is not None else False, results=self.search)
		stream = media.getbest()
		gui.Show()
		self.Hide()
		gui.player = Player(stream.url, gui.GetHandle())

	def playAudio(self):
		number = self.searchResults.Selection
		if self.search.get_type(number) == "playlist":
			return
		title = self.search.get_title(number)
		url = self.search.get_url(number)
		speak(_("جاري التشغيل"))
		media = pafy.new(url)
		gui = MediaGui(self, title, url, results=self.search, audio_mode=True)
		stream = media.getbestaudio()
		gui.Show()
		self.Hide()
		gui.player = Player(stream.url, gui.GetHandle())

	def onHook(self, event):
		if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER): # if the enter key was pressed
			self.playVideo() # play the video stream
		event.Skip()

	def onKeyDown(self, event):
		if event.controlDown and event.KeyCode == wx.WXK_SPACE:
			self.playAudio()
		event.Skip()
	def contextSetup(self):
		self.contextMenu = wx.Menu()

		videoPlayItem = self.contextMenu.Append(-1, _("تشغيل"))
		self.videoPlayItemId = videoPlayItem.GetId()
		audioPlayItem = self.contextMenu.Append(-1, _("التشغيل كمقطع صوتي"))
		self.audioPlayItemId = audioPlayItem.GetId()
		self.downloadMenu = wx.Menu()
		videoItem = self.downloadMenu.Append(-1, _("فيديو"))
		audioMenu = wx.Menu()
		m4aItem = audioMenu.Append(-1, "m4a")
		mp3Item = audioMenu.Append(-1, "mp3")
		self.downloadMenu.AppendSubMenu(audioMenu, _("صوت"))
		self.downloadId = self.contextMenu.AppendSubMenu(self.downloadMenu, _("تنزيل")).GetId()
		directDownloadItem = self.contextMenu.Append(-1, _("التنزيل المباشر...\tctrl+d"))
		self.directDownloadId = directDownloadItem.GetId()
		openChannelItem = self.contextMenu.Append(-1, _("الانتقال إلى القناة"))
		downloadChannelItem = self.contextMenu.Append(-1, _("تنزيل القناة"))
		copyItem = self.contextMenu.Append(-1, _("نسخ رابط المقطع"))
		webbrowserItem = self.contextMenu.Append(-1, _("الفتح من خلال متصفح الإنترنت"))
		def popup():
			if self.searchResults.Strings != []:
				self.searchResults.PopupMenu(self.contextMenu)
		self.searchResults.Bind(wx.EVT_MENU, lambda event: self.playVideo(), videoPlayItem)
		self.searchResults.Bind(wx.EVT_MENU, lambda event: self.playAudio(), audioPlayItem)
		self.searchResults.Bind(wx.EVT_MENU, self.onOpenChannel, openChannelItem)
		self.searchResults.Bind(wx.EVT_MENU, self.onDownloadChannel, downloadChannelItem)
		self.searchResults.Bind(wx.EVT_MENU, self.onCopy, copyItem)
		self.Bind(wx.EVT_MENU, self.onOpenInBrowser, webbrowserItem)
		self.searchResults.Bind(wx.EVT_CONTEXT_MENU, lambda event: popup())
		self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
		self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
		self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
		self.Bind(wx.EVT_MENU, lambda event: self.directDownload(), directDownloadItem)
	def onOpenChannel(self, event):
		n = self.searchResults.Selection
		webbrowser.open(self.search.get_channel(n)["url"])
	def onDownloadChannel(self, event):
		n = self.searchResults.Selection
		channel = self.search.get_channel(n)
		title = channel["name"]
		url = channel["url"]
		download_type = "channel"
		dlg = DownloadProgress(self.Parent, title)
		direct_download(int(config_get('defaultformat')), url, dlg, download_type)

	def onOpenInBrowser(self, event):
		number = self.searchResults.Selection
		url = self.search.get_url(number)
		webbrowser.open(url)
	def onDownload(self, event):
		downloadMenu = wx.Menu()
		videoItem = downloadMenu.Append(-1, _("فيديو"))
		audioMenu = wx.Menu()
		m4aItem = audioMenu.Append(-1, "m4a")
		mp3Item = audioMenu.Append(-1, "mp3")
		downloadMenu.Append(-1, _("صوت"), audioMenu)
		self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
		self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
		self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
		self.PopupMenu(downloadMenu)

	def onM4aDownload(self, event):
		url = self.search.get_url(self.searchResults.Selection)
		title = self.search.get_title(self.searchResults.Selection)
		download_type = self.search.get_type(self.searchResults.Selection)
		dlg = DownloadProgress(self.Parent, title)
		direct_download(1, url, dlg, download_type)

	def onMp3Download(self, event):
		url = self.search.get_url(self.searchResults.Selection)
		title = self.search.get_title(self.searchResults.Selection)
		download_type = self.search.get_type(self.searchResults.Selection)
		dlg = DownloadProgress(self.Parent, title)
		direct_download(2, url, dlg, download_type)

	def onVideoDownload(self, event):
		url = self.search.get_url(self.searchResults.Selection)
		title = self.search.get_title(self.searchResults.Selection)
		download_type = self.search.get_type(self.searchResults.Selection)
		dlg = DownloadProgress(self.Parent, title)
		direct_download(0, url, dlg, download_type)



	def onCopy(self, event):
		pyperclip.copy(self.search.get_url(self.searchResults.Selection))
		wx.MessageBox(_("تم نسخ رابط المقطع بنجاح"), _("اكتمال"), parent=self)
	def loadMore(self):
		if self.searchResults.Strings == []:
			return
		speak(_("جاري تحميل المزيد من النتائج"))
		if self.search.load_more() is None:
			speak(_("لم يتمكن البرنامج من تحميل المزيد من النتائج"))
			return
		# position = self.searchResults.Selection
		wx.CallAfter(self.searchResults.Append, self.search.get_last_titles())
		speak(_("تم تحميل المزيد من نتائج البحث"))
		wx.CallAfter(self.searchResults.SetFocus)
	def onListBox(self, event):
		self.togleDownload()
		self.toglePlay()
		if self.searchResults.Selection == len(self.searchResults.Strings)-1:
			if not config_get("autoload"):
				self.loadMoreButton.Enabled = True
				return
			Thread(target=self.loadMore).start()
		else:
			self.loadMoreButton.Enabled = False
	def onLoadMore(self, event):
		Thread(target=self.loadMore).start()
	def backAction(self):
		self.Destroy()
		self.Parent.Show()
	def togleControls(self):
		if self.searchResults.Strings == []:
			for control in self.panel.GetChildren():
				if control.Name == "controls":
					control.Hide()
			self.loadMoreButton.Hide()
		else:
			for control in self.panel.GetChildren():
				if control.Name == "controls":
					control.Show()
			self.loadMoreButton.Show(not config_get("autoload"))
	def togleDownload(self):
		n = self.searchResults.Selection
		if self.search.get_views(n) is None and self.search.get_type(n) == "video":
			self.contextMenu.Enable(self.downloadId, False)
			self.contextMenu.Enable(self.directDownloadId, False)
			self.downloadButton.Enabled = False
			return
		self.contextMenu.Enable(self.downloadId, True)
		self.contextMenu.Enable(self.directDownloadId, True)
		self.downloadButton.Enabled = True

	def toglePlay(self):
		n = self.searchResults.Selection
		contextMenuIds = (self.videoPlayItemId, self.audioPlayItemId)
		if self.search.get_type(n) == "playlist":
			self.playButton.Enabled = False
			for i in contextMenuIds:
				self.contextMenu.Enable(i, False)
			return
			self.playButton.Enabled = True
			for i in contextMenuIds:
				self.contextMenu.Enable(i, True)

	def directDownload(self):
		n = self.searchResults.Selection
		if self.search.get_views(n) is None and self.search.get_type(n) == "video":
			return
		url = self.search.get_url(self.searchResults.Selection)
		title = self.search.get_title(self.searchResults.Selection)
		download_type = self.search.get_type(self.searchResults.Selection)
		dlg = DownloadProgress(self.Parent, title)
		direct_download(int(config_get('defaultformat')), url, dlg, download_type)
	def onShow(self, event):
		self.searchResults.SetFocus()

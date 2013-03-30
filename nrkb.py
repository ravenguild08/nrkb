#!/usr/bin/python

"""
nrkb.py
peter hung | phung@post.harvard.edu
 2013-3-18 | 3-29

implements nurikabe view and controller with wxPython

NrkbBoard handles mouse events and requests and recieves changes from the controller
NrkbController has
- NrkbBoard that it receives requests and pushes updates to
- a Game, which is pretty much an array that stores stuff
- a Grid, that invokes check() and solve(), both which are able to push updates to the controller

"""

import wx
import threading
import os
import sys
import time
import nrkb_logic
import nrkb_fctrl
from Queue import Queue

WATER = nrkb_logic.WATER
ISLAND = nrkb_logic.ISLAND
BLANK = nrkb_logic.BLANK
INFER = nrkb_logic.INFER
GameState = nrkb_logic.GameState

class BoundsError(Exception):
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return repr(self.value)

# a panel which listens for clicks, translates and sends commands to controller
class NrkbBoard(wx.Panel):
  def __init__(self, controller, rows, cols):
    self.rows = rows
    self.cols = cols
    self.width = 24
    self.size = (self.width * self.cols, self.width * self.rows)
    wx.Panel.__init__(self, controller, size = self.size)
    self.controller = controller
    self.font = wx.Font(self.width / 2 + 2, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False, 'Courier 10 Pitch')
    self.prev = -1, -1
    self.cursor = WATER

    # setup mouse handlers
    self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
    self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)    
    self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
    self.Bind(wx.EVT_RIGHT_DCLICK, self.OnRightDown)
    self.Bind(wx.EVT_PAINT, self.OnPaint)
    self.Bind(wx.EVT_MOTION, self.OnMouseMove)

  # convert UI x, y into x and y of board, throwing bounds error if out of bounds
  def coordsOfPos(self, pos):
    x = pos[0] / self.width
    y = pos[1] / self.width
    if x >= self.rows or x < 0 or y >= self.cols or y < 0:
      raise BoundsError('(' + str(x) + ' ,' + str(y) + ') out of bounds')
    else:
      return x, y

  # when clicked ask the controller for the current state, then and asks to change the region
  def OnLeftDown(self, event):
    if self.controller.locked():
      return
    self.prev = -1, -1
    try:
      coords = self.coordsOfPos(event.GetPosition())
    except BoundsError:
      event.Skip()
      return

    # either mark as stream or set to unmarking
    state = self.controller.fetchGame(coords)
    if state == WATER:
      self.cursor = BLANK
    else:
      self.cursor = WATER

    self.controller.changeGame(coords, self.cursor)
  # when clicked ask the controller for the current state, then and asks to change the region
  def OnRightDown(self, event):
    if self.controller.locked():
      return
    self.prev = -1, -1
    try:
      coords = self.coordsOfPos(event.GetPosition())
    except BoundsError:
      event.Skip()
      return

    # either mark as island or set to unmarking
    state = self.controller.fetchGame(coords)
    if state == ISLAND:
      self.cursor = BLANK
    else:
      self.cursor = ISLAND

    self.controller.changeGame(coords, self.cursor)

  # when it moves into another region, attempt to color that region
  def OnMouseMove(self, event):
    if self.controller.locked():
      return
    # do nothing if the mouse is not pressed right now
    if not event.LeftIsDown() and not event.RightIsDown():
      event.Skip()
      return

    # whenever the mouse is moved
    try:
      coords = self.coordsOfPos(event.GetPosition())
    except BoundsError:
      event.Skip()
      return

    # if haven't moved into the next area, skip
    if coords[0] == self.prev[0] and coords[1] == self.prev[1]:
      return
    self.prev = coords

    self.controller.changeGame(coords, self.cursor)

  # draw entire grid, either manually or with Paint handler
  def OnPaint(self, event):
    dc = wx.PaintDC(self)
    game = self.controller.game
    for y in range(self.rows):
      for x in range(self.cols):        
        self.drawSquare((x, y), game.board[y][x], False, dc)

  # draws all regions on board, defaulting to controller's game if none is passed
  def drawBoard(self, game = None):
    dc = wx.ClientDC(self)
    if not game:
      game = self.controller.game
    for y in range(self.rows):
      for x in range(self.cols):        
        self.drawSquare((x, y), game.board[y][x], False, dc)

  # draws the pointed to square as state, red if flagged
  def drawSquare(self, (x, y), state, flagged, dc = None):
    if dc == None:
      dc = wx.ClientDC(self)
    if flagged:
      color = '#FF0000'
    else:
      color = '#000000'
    dc.SetPen(wx.Pen(color))
    dc.SetFont(self.font)
    # if marked as stream, draw as black rectangle
    if state == WATER:
      dc.SetBrush(wx.Brush(color))
    else:
      dc.SetBrush(wx.Brush('#eeeeee'))

    # draw out a square
    dc.DrawRectangle(x * self.width, y * self.width, self.width, self.width)        
    
    # if a numbered island, draw text
    if state > 0:
      string = str(state)
      w, h = dc.GetTextExtent(string)
      dc.DrawText(string, x * self.width - w/2 + self.width / 2, y * self.width)
    # if marked as islands, fill in with a period
    elif state == ISLAND or state == INFER:
      w, h = dc.GetTextExtent('.')
      dc.DrawText('.', x * self.width - w/2 + self.width / 2, y * self.width - h/4)

class HighScores(wx.Dialog):
  def __init__(self, *args, **kwargs):
    kwargs['title'] = 'High Scores'
    kwargs['size'] = (400, 225)
    wx.Dialog.__init__(self, *args, **kwargs)

    fgs = wx.FlexGridSizer(7, 4, 5, 20)
    scores = nrkb_fctrl.get_scores()
    header_font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    headers = [wx.StaticText(self, label = 'Size'), 
              wx.StaticText(self, label = 'Time'), 
              wx.StaticText(self, label = 'Player'), 
              wx.StaticText(self, label = 'Date Achieved')]
    for header in headers:
      header.SetFont(header_font)
    fgs.AddMany(headers)
    for size, (score, user, date) in sorted(scores.items(), key = lambda (k, v): int(k)):
      sizet = wx.StaticText(self, label = str(size) + 'x' + str(size))
      sizet.SetFont(header_font)
      if score != -1:
        if score > 60:
          s, ms = divmod(score, 1)
          m, s = divmod(score, 60)
          score_str = ('%d:%02d:%02d' % (m, s, ms * 100))
        else:
          score_str = ('%.2f' % score)
        if len(user) > 20:
          user = user[:17] + '...'
        scoret = wx.StaticText(self, label = score_str)
        usert = wx.StaticText(self, label = user)
        datet = wx.StaticText(self, label = time.strftime('%c', time.localtime(date)))
      else:
        scoret = wx.StaticText(self, label = '--:--.--')
        usert = wx.StaticText(self, label = '')
        datet = wx.StaticText(self, label = '')
      fgs.AddMany([sizet, scoret, usert, datet])

    okb = wx.Button(self, id = wx.ID_OK, label = 'OK')
    clearb = wx.Button(self, id = wx.ID_CLEAR, label = 'Clear History')
    self.Bind(wx.EVT_BUTTON, self.OnClear, clearb)
    vbox = wx.BoxSizer(wx.VERTICAL)
    hbox = wx.BoxSizer(wx.HORIZONTAL)
    hbox.Add(okb, flag = wx.RIGHT | wx.ALIGN_CENTER, border = 15)
    hbox.Add(clearb, flag = wx.LEFT | wx.ALIGN_CENTER, border = 15)
    vbox.Add(fgs, flag = wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border = 10)
    vbox.Add(wx.StaticLine(self, -1, size = (300, 1), style = wx.LI_HORIZONTAL), flag = wx.ALIGN_CENTER)
    vbox.Add(hbox, flag = wx.ALL | wx.ALIGN_CENTER, border = 10)
    self.SetSizer(vbox)
    self.Layout()

  def OnClear(self, event):
    nrkb_fctrl.init_scores()
    self.Destroy()

    
    
    
class NrkbController(wx.Frame):
  def __init__(self, parent, rows, cols, index):
    super(NrkbController, self).__init__(parent, title='nrkb', style=wx.DEFAULT_FRAME_STYLE & (~wx.RESIZE_BORDER) & (~wx.MAXIMIZE_BOX))
    self.rows = rows
    self.cols = cols
    self.InitUI()

    # go fetch the icon and use it
    directory = os.getcwd()
    icon = wx.Icon(directory + '/nrkb.ico', wx.BITMAP_TYPE_ICO)
    self.SetIcon(icon)

    # create a new game
    self.newGame(index)
    self.resize()

    self.board.SetFocus()
    self.Centre()
    self.Show(True)

  def InitUI(self):
    # create file menu
    fileMenu = wx.Menu()
    newi = fileMenu.Append(wx.ID_NEW, '&New\tF2', 'Start new game')
    cleari = fileMenu.Append(wx.ID_CLEAR, '&Clear\tF3', 'Clear this game')
    statisticsi = fileMenu.Append(wx.ID_ANY, '&High Scores\tF4', 'See high scores')  
    preferencesi = fileMenu.Append(wx.ID_PREFERENCES, '&Preferences\tF5', 'Alter game prefences')  
    fileMenu.AppendSeparator()
    quiti = fileMenu.Append(wx.ID_EXIT, '&Quit\tCtrl+Q', 'Quit application')
    
    # create a help menu
    helpMenu = wx.Menu()
    helpi = helpMenu.Append(wx.ID_HELP, '&Help\tF1', 'Instructions')
    abouti = helpMenu.Append(wx.ID_ABOUT, '&About', 'About Nurikabe')
    helpMenu.AppendSeparator()
    refreshi = fileMenu.Append(wx.ID_REFRESH, 'Chec&k\tSpace', 'Check this game')
    solvei = helpMenu.Append(wx.ID_ANY, '&Start Solve\tF9', 'Watch it solve itself')
    stopi = helpMenu.Append(wx.ID_ANY, '&Kill Solve\tF10', 'Kill the solve')

    # create menubar and buttons
    menubar = wx.MenuBar()
    menubar.Append(fileMenu, '&File')
    menubar.Append(helpMenu, '&Help')
    self.SetMenuBar(menubar)

    # bind menu buttons to events    
    self.Bind(wx.EVT_MENU, self.OnNew, newi)
    self.Bind(wx.EVT_MENU, self.OnClear, cleari)
    self.Bind(wx.EVT_MENU, self.OnCheck, refreshi)
    self.Bind(wx.EVT_MENU, self.OnStatistics, statisticsi)
    self.Bind(wx.EVT_MENU, self.OnPreferences, preferencesi)
    self.Bind(wx.EVT_MENU, self.OnQuit, quiti)
    self.Bind(wx.EVT_MENU, self.OnHelp, helpi)
    self.Bind(wx.EVT_MENU, self.OnAbout, abouti)
    self.Bind(wx.EVT_MENU, self.OnSolve, solvei)
    self.Bind(wx.EVT_MENU, self.OnStop, stopi)

    # create a status bar
    self.sb = self.CreateStatusBar()
    self.sb.SetFieldsCount(2)

    # create a new board panel, align it in sizers
    self.board = NrkbBoard(self, self.rows, self.cols)
    vbox = wx.BoxSizer(wx.VERTICAL)
    hbox = wx.BoxSizer(wx.HORIZONTAL)
    hbox.Add(self.board, 1, wx.ALL, 0)
    vbox.Add(hbox, 1, wx.ALL, 0)
    self.SetSizer(vbox)

    # create a timer
    ID_TIMER = 1
    self.timer = wx.Timer(self, ID_TIMER)
    self.Bind(wx.EVT_TIMER, self.OnTimer, id=ID_TIMER)
    
  # fetches a new game
  def OnNew(self, event):
    self.newGame()
  # requests board to be cleared
  def OnClear(self, event):
    self.clearGame()
  # checks the game, which also redraws flagged squares
  def OnCheck(self, event):
    self.checkGame()
  # asks for solution
  def OnSolve(self, event):
    self.startSolveGame()  
  # kills the solution thread
  def OnStop(self, event):
    self.stopSolveGame()
  # displays high scores dialog box
  def OnStatistics(self, event):
    score_dialog = HighScores(self)
    score_dialog.Show(True)
  # displays size option dialog box, then starts a new game if a new size is selected
  def OnPreferences(self, event):
    values = [5, 7, 10, 12, 15, 20]
    choices = map(lambda x: str(x) + 'x' + str(x), values)
    opts = wx.SingleChoiceDialog(self, 'Select a size.', 'Nurikabe Options', choices)
    opts.SetSize((250, 200))
    opts.SetSelection(values.index(self.rows))
    if opts.ShowModal() == wx.ID_OK:
      ix = opts.GetSelection()
      self.rows = values[ix]
      self.cols = values[ix]
      self.newGame()
    opts.Destroy()  
  # stops any solves and kills parent thread
  def OnQuit(self, event):
    self.timer.Stop()
    self.stopSolveGame()
    self.Close()
  # displays instruction dialog
  def OnHelp(self, event):
    wx.MessageBox("""You have a grid of squares, some of which start with numbers. The goal is to color the grid black or white according to these rules:\n- The white squares will form "islands". Each island must have one number and exactly that many white squares.\n- The black squares will form the stream, or "nurikabe", which come together to form a single polymino, which must not contain any 2x2 "puddles".\nLeft click on a square to color it black. Right click to mark it with a dot, which colors it white. Click and drag to mark more than one square.\n""", 'Nurikabe Instructions', wx.OK | wx.ICON_INFORMATION)
  # displays about dialog
  def OnAbout(self, event):
    info = wx.AboutDialogInfo()
    #info.SetIcon(wx.Icon('xxx.png', wx.BITMAP_TYPE_PNG))
    info.SetName('nrkb')
    info.SetVersion('1.2')
    info.SetDescription("""A Nurikabe engine and solver.\nBoards from puzzle-nurikabe.com.""")
    info.SetCopyright('(C) 2013')
    info.AddDeveloper('Peter Hung')
    #info.SetWebSite('phung@post.harvard.edu')
    wx.AboutBox(info)
  # called every tenth second, asks status to be updated
  def OnTimer(self, event):
    self.updateStatus()

  # this function is called all the time, every tenth second and after every interaction
  def updateStatus(self):
    if self.status == GameState.SOLVED:
      self.timer.Stop()
    time_str = str(round(time.time() - self.start, 1))
    state_str = str(self.status)
    self.sb.SetFields([state_str, time_str])
    self.drawQueue()
  # asks board for its size and resizes frame around it. calibrated for windows 7 aero
  def resize(self):
    width, height = self.board.size
    width += 6
    height += 71
    self.SetSize((width, height))
    self.SetAutoLayout(True)
    self.Layout()
  # check stores the result in self.status
  def locked(self):
    return self.status == GameState.SOLVED or self.grid.solving

  # functions that the view calls. changeGame() interacts with the game
  def fetchGame(self, coords):
    return self.game.getState(coords)
  def changeGame(self, coords, state, from_queue = False):
    if self.status != GameState.SOLVED or from_queue:
      changed = self.game.setState(coords, state)
      if changed: 
        self.board.drawSquare(coords, state, False)
  def flagGame(self, coords, state):
    self.board.drawSquare(coords, state, True)

  # what the grid calls while it's solving to push changes to be drawn
  def queueChange(self, coords, state):
    self.queue.put((coords, state))

  # while solving, the queue will be filled with changes to draw. this handles them
  def drawQueue(self):
    while not self.queue.empty():
      coords, state = self.queue.get()
      self.changeGame(coords, state, True)

  # only functions that interact with the game or grid
  def newGame(self, index = -1):
    if hasattr(self, 'grid'):
      self.stopSolveGame()
    self.game = nrkb_logic.Game(self.rows, self.cols, index)
    self.grid = nrkb_logic.Grid(self.game)
    self.queue = Queue()
    self.status = GameState.OKAY
    self.disqualified = False
    # if requesting a new board size, destroy old UI
    if self.rows != self.board.rows or self.cols != self.board.cols:
      self.board.Destroy()
      self.board = NrkbBoard(self, self.game.rows, self.game.cols)
      self.resize()
    else:
      self.board.drawBoard()
    self.SetTitle('nrkb ' + str(self.game.rows) + 'x' + str(self.game.cols) + ' #' + str(self.game.index))
    self.start = time.time()
    self.timer.Start(100)
    self.updateStatus()
  def clearGame(self):
    self.stopSolveGame()
    self.game.clear()
    self.grid.copy_game(self.game)
    self.status = GameState.OKAY
    self.board.drawBoard()
    if not self.timer.IsRunning():
      self.timer.Start()
  def checkGame(self):
    if self.locked():
      return
    if self.status == GameState.ERROR:
      self.board.drawBoard()      
    self.grid.copy_game(self.game)
    self.status = self.grid.check(self)
    if self.status == GameState.ERROR:
      self.disqualified = True
    elif self.status == GameState.SOLVED and not self.disqualified:
      self.logScore(self.rows, time.time() - self.start, time.time())

  # called when user completes game. asks for a name, logs score, shows dialog
  def logScore(self, size, score, date):
    if not nrkb_fctrl.is_better(size, score):
      return
    ted = wx.TextEntryDialog(self, 'New best time! Enter your name:', 'High Score', defaultValue = 'Name')
    ted.SetSize((200, 150))
    if ted.ShowModal() == wx.ID_OK:
      name = ted.GetValue()
      nrkb_fctrl.set_score(size, score, name, date)
      score_dialog = HighScores(self)
      score_dialog.Show(True)

  def startSolveGame(self):
    if self.locked():
      return
    if not self.grid.solving:
      wx.BeginBusyCursor()
    self.disqualified = True
    self.grid.solving = True
    self.queue = Queue()
    solver_thread = threading.Thread(target=self.grid.solve, args = [self])
    solver_thread.daemon = True
    solver_thread.start()

  # tell grid to stop solving by setting attribute
  def stopSolveGame(self):
    if self.grid.solving:
      wx.EndBusyCursor()
    self.grid.solving = False
    self.drawQueue()

    # resync board if the draw queue messed up earlier, which is actually pretty likely
    for y in range(self.rows):
      for x in range(self.cols):
        self.game.board[y][x] = self.grid.s[y][x].state
    self.board.drawBoard()


# main method!
if __name__ == '__main__':
  # if run by cmd, parse out size and index
  sizes = [5, 7, 10, 12, 15, 20]
  size = 10
  index = -1
  if len(sys.argv) >= 2:
    size = int(sys.argv[1])
    if size not in sizes:
      print 'that\'s not a valid size! returning.'
      sys.exit(1)
  if len(sys.argv) >= 3:
    index = int(sys.argv[2])

  # initialize the controller, then let it run
  app = wx.App()
  NrkbController(None, size, size, index)
  app.MainLoop()
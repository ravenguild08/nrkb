#!/usr/bin/python

"""
nrkb.py
peter hung | phung@post.harvard.edu
2013-3-18 | 3-27

implements an nurikabe UI with wx python. the view and the controller are included here


the view handles mouse events and requests and recieves changes from the controller
class NrkbBoard:
  drawSquare((x, y), state, flagged)
  drawBoard(game)

class NrkbController: 
  it owns:
  - NrkbBoard to show stuff
  - Game where it saves all the info
  - Grid which it invokes to check() and solve()

  changeGame((x, y), state)
  fetchGame((x, y))

TODO: change timer so that it uses time.time() instead
TODO: change how grid.check() is called so that it's universal
"""

import wx
import threading
import os
import sys
import time
import nrkb_logic

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
    self.locked = False

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
    if self.locked:
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
    if self.locked:
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
    if self.locked:
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
    preferencesi = fileMenu.Append(wx.ID_PREFERENCES, '&Preferences\tF5', 'Alter game prefences')  
    fileMenu.AppendSeparator()
    refreshi = fileMenu.Append(wx.ID_REFRESH, 'Chec&k\tSpace', 'Check this game')
    solvei = fileMenu.Append(wx.ID_ANY, 'Start Solve\tDelete', 'Watch it solve itself')
    stopi = fileMenu.Append(wx.ID_ANY, 'Kill Solve\t`', 'Kill the solve')
    fileMenu.AppendSeparator()
    quiti = fileMenu.Append(wx.ID_EXIT, 'Quit\tCtrl+Q', 'Quit application')
    
    # create a help menu
    helpMenu = wx.Menu()
    helpi = helpMenu.Append(wx.ID_HELP, '&Help\tF1', 'Instructions')
    abouti = helpMenu.Append(wx.ID_ABOUT, '&About', 'About Nurikabe')

    # create menubar and buttons
    menubar = wx.MenuBar()
    menubar.Append(fileMenu, '&File')
    menubar.Append(helpMenu, '&Help')
    self.SetMenuBar(menubar)

    # bind menu buttons to events    
    self.Bind(wx.EVT_MENU, self.OnNew, newi)
    self.Bind(wx.EVT_MENU, self.OnClear, cleari)
    self.Bind(wx.EVT_MENU, self.OnCheck, refreshi)
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
    self.updateStatus()
  # requests board to be cleared
  def OnClear(self, event):
    self.clearGame()
    self.updateStatus()
  # checks the game, which also redraws flagged squares
  def OnCheck(self, event):
    self.checkGame()
    self.updateStatus()
  # asks for solution
  def OnSolve(self, event):
    self.startSolveGame()  
    self.updateStatus()
  # kills the solution thread
  def OnStop(self, event):
    self.stopSolveGame()
    self.updateStatus()
  # displays size option dialog box, then starts a new game if a new size is selected
  def OnPreferences(self, event):
    values = [5, 7, 10, 12, 15, 20]
    choices = map(lambda x: str(x) + 'x' + str(x), values)
    opts = wx.SingleChoiceDialog(self, 'Select a size.', 'Nurikabe Options', choices)
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
    wx.MessageBox("""You have a grid of squares, some of which start with numbers. The goal is to color the grid black or white according to these rules:
- The white squares will form "islands". Each island must have one number and exactly that many white squares.
- The black squares will form the stream, or "nurikabe", which come together to form a single polymino, which must not contain any 2x2 "puddles".
Left click on a square to color it black. Right click to mark it with a dot, which colors it white. Click and drag to mark more than one square.
""", 'Nurikabe Instructions', wx.OK | wx.ICON_INFORMATION)
  # displays about dialog
  def OnAbout(self, event):
    info = wx.AboutDialogInfo()
    #info.SetIcon(wx.Icon('xxx.png', wx.BITMAP_TYPE_PNG))
    info.SetName('Nurikabe')
    info.SetVersion('1.0')
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
    if self.gameState == GameState.SOLVED:
      self.timer.Stop()
    time_str = str(round(time.time() - self.start, 1))
    state_str = str(self.gameState)
    self.sb.SetFields([state_str, time_str])
  # asks board for its size and resizes frame around it. calibrated for windows 7 aero
  def resize(self):
    width, height = self.board.size
    width += 6
    height += 71
    self.SetSize((width, height))
    self.SetAutoLayout(True)
    self.Layout()
  # check stores the result in self.gameState
  def locked(self):
    return self.gameState == GameState.SOLVED or self.grid.solving

  # functions that the view calls. changeGame() interacts with the game
  def fetchGame(self, coords):
    return self.game.getState(coords)
  def changeGame(self, coords, state):
    if self.gameState != GameState.SOLVED:
      changed = self.game.setState(coords, state)
      if changed: 
        self.board.drawSquare(coords, state, False)
  # TODO: deprecate, and have check pass back a flag matrix instead
  def flagGame(self, coords, state):
    self.board.drawSquare(coords, state, True)

  # when passed a game, updates the owned game to become the other. called by the model
  def updateGame(self, game = None):
    if game:
      for y in range(self.rows):
        for x in range(self.cols):
          self.game.board[y][x] = game.board[y][x]
    self.board.drawBoard()

  # only functions that interact with the game or grid
  def newGame(self, index = -1):
    if hasattr(self, 'grid'):
      self.stopSolveGame()
    self.game = nrkb_logic.Game(self.rows, self.cols, index)
    self.grid = nrkb_logic.Grid(self.game)
    self.gameState = GameState.OKAY
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
    self.gameState = self.grid.check()
    self.board.drawBoard()
    if not self.timer.IsRunning():
      self.timer.Start()
  def checkGame(self):
    if self.locked():
      return
    if self.gameState == GameState.ERROR:
      self.board.drawBoard()      
    self.grid.copy_game(self.game)
    # TODO: have check pass back a gameState and a flag matrix, then draw here
    self.gameState = self.grid.check(self)
  def startSolveGame(self):
    if self.locked():
      return
    if not self.board.locked:
      wx.BeginBusyCursor()
      # TODO: funnily enough, there are two distinct ways to lock the board. combine them?
      self.board.locked = True
    # TODO: catch errors?
    solver_thread = threading.Thread(target=self.grid.solve, args = [self])
    solver_thread.daemon = True
    solver_thread.start()
  # tell grid to stop solving by setting attribute, then updated the game state and all
  def stopSolveGame(self):
    self.grid.solving = False
    self.gameState = self.grid.check()
    if self.board.locked:
      self.board.locked = False
      wx.EndBusyCursor()

# main method!
if __name__ == '__main__':
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

  app = wx.App()
  NrkbController(None, size, size, index)
  app.MainLoop()
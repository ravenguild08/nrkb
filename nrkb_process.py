#!/usr/bin/env python

'''
nrkb_fctrl.py
peter hung | phung@post.harvard.edu
2013-3-18 | 3-23

simple scripting file that takes a formatted load.txt and appends a translated
board to the appropriate #x#.txt
'''

import nrkb_fctrl

# takes block of assumes newline then space separated numbers, returns 2d matrix
# ensures it's square throwing KeyError if not
def read_board_string(text):
  def parse(s):
    try:
      return int(s)
    except ValueError:
      return 0

  board = []
  for line in text.split('\n'):
    row = map(parse, line.split())
    if len(row) > 0:
      board.append(row)

  rows = len(board[0])
  cols = len(board)

  if rows == 0 or cols == 0 or any(map(lambda x: len(x) != rows, board)):
    raise KeyError
  return board

# looks at a filename and appends translated board to file if appropriate
def process(filename):
  textfile = open(filename, 'r')
  text = textfile.read()
  textfile.close()
  try:
    board = read_board_string(text)
    nrkb_fctrl.save_board(board)
    print board
  except KeyError:
    print 'failed to read a good board'
    return

process('load.txt')
#!/usr/bin/env python

'''
nrkb_fctrl.py

peter hung | phung@post.harvard.edu
2013-3-18 | 3-23

implements interactions with board data files, named [rows]x[cols].json
'''

import json
import os
import random
import string

sizes = [5, 7, 10, 12, 15, 20]

def filename(rows, cols = None):
  if cols == None:    
    cols = rows
  return str(rows) + 'x' + str(cols) + '.json'

# returns number of characters per board. will be wrong per double digit seed
def chars_per_board(rows, cols = None):
  if cols == None:
    cols = rows
  return rows * (3 * cols) + rows * 2 + 2

# by judging file sizes, returns estimated number of saved boards in a file
def num_boards(rows, cols = None):
  if cols == None:
    cols = rows
  name = filename(rows, cols)
  if not os.path.exists(name):
    return -1
  total = os.path.getsize(name)
  line_len = chars_per_board(rows, cols)
  return int(round(total / line_len))

# takes a board and appends a json-encoded string to the end of file
def save_board(board):
  data = json.dumps(board)
  rows = len(board)
  cols = len(board[0])
  outfile = open(filename(rows, cols), 'a')
  outfile.write(data + '\n')
  outfile.close()

# scans to approximate line, reads board, and returns the (board, index) it chose
def load_board(rows, cols, index = -1):
  try:
    infile = open(filename(rows, cols), 'r')
  except IOError, KeyError:
    return None    

  line_len = chars_per_board(rows, cols)
  count = num_boards(rows, cols)
  if count == 0:
    return None

  # if no index specified, choose a random board
  if index <= 0:
    index = random.randint(0, count - 1)
  else:
    index = int(index - 1) % count

  # if not first trivially obtain board, seek to about halfway before requested board
  if index > 0:
    infile.seek((index - 1) * line_len + int(line_len / 2), 0)
    infile.readline()
  line = infile.readline()
  board = json.loads(line)
  infile.close()
  return board, index + 1

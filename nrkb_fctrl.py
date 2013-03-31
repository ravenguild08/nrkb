#!/usr/bin/env python

'''
nrkb_fctrl.py

peter hung | phung@post.harvard.edu
 2013-3-18 | 2013-3-29

implements interactions with board data files, named [rows]x[cols].json
stores and loads fastest times in a visible json file
  the high scores assume only 6 square board sizes

'''

import json
import os
import random
import string
import time

sizes = [5, 7, 10, 12, 15, 20]
SCORE_FILE = 'scores.json'

# returns [rows]x[cols].json
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

# scans to approximate line, reads board, and returns the (board, index)
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

  # if not first trivially obtainable board, seek to about a half board before it
  if index > 0:
    infile.seek((index - 1) * line_len + int(line_len / 2), 0)
    infile.readline()

  # read the line, convert it to a board, and return the board and index
  line = infile.readline()
  infile.close()
  board = json.loads(line)
  return board, index + 1

# returns a list of (size, time, name) tuples. assumes the size square board sizes
def get_scores():
  try:
    infile = open(SCORE_FILE, 'r')
  except IOError:
    return init_scores()
  text = infile.read()
  scores = json.loads(text)
  return scores

# returns true if the passed score is better than the stored one per size
def is_better(size, score):
  if size not in sizes:
    return False
  scores = get_scores()
  old = scores[str(size)][0]
  if old == -1 or score < old:
    return True
  return False

# when passed a time, replaces previous best only if it is faster
def set_score(size, score, user, date = None):
  if size not in sizes:
    return False
  scores = get_scores()
  old = scores[str(size)][0]
  if old == -1 or score < old:
    if date == None:
      date = time.time()
    scores[str(size)] = (score, user, date)
    try:
      outfile = open(SCORE_FILE, 'w')
    except IOError:
      return
    text = json.dumps(scores, indent = 2)
    outfile.write(text)
    outfile.close()
    return True
  return False

# blindly wipes out the score file
def init_scores():
  scores = {}
  for size in sizes:
    scores[str(size)] = ((-1, '', None))
  try:
    outfile = open(SCORE_FILE, 'w')
  except IOError:
    return scores
  text = json.dumps(scores, indent = 2)
  outfile.write(text)
  outfile.close()
  return scores

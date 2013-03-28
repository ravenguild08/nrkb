#!/usr/bin/env python

'''
nrkb_debug.py
peter hung | phung@post.harvard.edu
2013-3-19 | 3-23

script that creates a game, a grid, and calls solve
'''

import nrkb_logic
import sys

if __name__ == '__main__':
  # parse size and index arguments if specified
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

  # create a new game
  game = nrkb_logic.Game(size, size, index)
  grid = nrkb_logic.Grid(game)
  grid.solve()
  
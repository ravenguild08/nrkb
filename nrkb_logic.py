#!/usr/bin/python

"""
  nrkb_logic.py
  peter hung | phung@post.harvard.edu
   2013-3-18 | 2013-3-30

  implements game logic of nurikabe.

  a Game is little more than an array of 0 if blank, 1 if island, 2 if water, and > 0 if a seed
  - when initialized, searched appropriately sized text file of json boards and loads one

  a Grid is foremost an array of Spaces, which know each other's neighbors and calculates things using Groups
  - check() tells every group to infer its group, waters first to fill in some states with infer
    * realizes most locally-detectable errors
      - if multiple seeds are connected by islands, or if it has too many islands
      - if several seeds are confined to too small a space
      - if an unseeded island is surrounded by water
      - if water has a puddle
      - if water is completely surrounded by island      
    * intelligently tells the controller to flag wrong regions
  - solve() uses groups, and remembered owners and a reacher map and logged owners of islands
    * tells controller it to update squares as they're deduced
    * slowly colors in one space at a time, queuing neighbors to be checked later
    * local rules:
      - if water only has one dof, continue water there
      - if island still needs more but only has one dof, continue island there
      - if island is complete, surround with water
      - if blank is neighbored by two differente islands, color as water
    * if space can't be reached by an island, color as water
      - only blanks and anonymous islands have reacher lists, the rest have owners
      - the reacher map is simple recursion for seeds that have no separate isles
      - for those with exactly one separate island, recursively attempt to chain
        from one side to the other. for every chain possibility, temporarily pretend
        it's a group and find out the reachers. the actual reachers are the union of all
        chains and reachers per chain. incidentally, it realizes that some spaces need to be
        islands if it appears in every chain
    * if coloring a square water would create a puddle, color as island
    * if an island has only one space left but either place it can place it borders
      the same square, i.e. a fork shape, color square as island
    * if square of four is made of two adjacent waters and two adjacent blanks that
      can only be reached by the same seed, attempt to chain to both
      - any space that appears in both chains or each other's chains must be islands
    * repeats until no changes have been made

    * repeats guesses of depth one, only retaining those which its sure its right. this solves nearly all boards

    * recursively guesses on space at a time and searches the recursion tree until it encounters the solution

  - TODO:
    * improve the guessing order. a spiral pattern or something would be good
    * completely overhaul group unification so that groups don't need to be forgotton and generated all the time
"""

from Enum import Enum
import nrkb_fctrl
import random
import time

loop_count = 0
grouped_count = 0
processed_count = 0
guessed_count = 0

BLANK = 0
ISLAND = -1
WATER = -2
INFER = -3
def state_str(state):
  if state == WATER:
    return '#'
  elif state == ISLAND:
    return 'o'
  elif state == BLANK:
    return '.'
  elif state == INFER:
    return 'x'
  else:
    return str(state)

GameState = Enum(['OKAY', 'SOLVED', 'ERROR'])
Type = Enum(['WATER', 'ISLAND', 'INCOMPLETE', 'INVALID_ISLAND', 'LONE_ISLAND',
              'LONE_BLANK', 'INVALID_WATER', 'CLOSED_WATER'])

# the class that's visible to the controller. dimensions and state matrix
class Game(object):
  def __str__(self):
    return '\n'.join(' '.join(state_str(state) for state in row) for row in self.board)
  def __repr__(self):
    return str(self)
  def __init__(self, rows, cols, index = -1, grid = None):
    self.rows = rows
    self.cols = cols
    self.index = 0
    if grid == None:
      # read in random board of appropriate size
      self.board, self.index = nrkb_fctrl.load_board(self.rows, self.cols, index)
      if self.board == None:
        self.board = [[BLANK for x in range(self.cols)] for y in range(self.rows)]
    else:
      self.board =[[space.state for space in row] for row in grid.s]
  # clear out any non-number states
  def clear(self):
    for y in range(self.rows):
      for x in range(self.cols):
        if self.board[y][x] <= 0:
          self.board[y][x] = BLANK
  # returns state of specified tuple coordinates
  def getState(self, (x, y)):
    if y < 0 or y >= self.rows or x < 0 or x >= self.cols:
      return BLANK
    return self.board[y][x]
  # attempts to set state at tuple coordinates, returning false if number there
  def setState(self, (x, y), state):
    space = self.board[y][x]
    if space <= BLANK and space != state:
      self.board[y][x] = state
      return True
    return False

class Grid(object):
  def __str__(self):
    return '\n'.join(' '.join(state_str(space.state) for space in row) for row in self.s) + '\n'
  def __repr__(self):
    return str(self)
  def __init__(self, game):
    self.rows = game.rows
    self.cols = game.cols
    self.seeds = []
    self.solving = False

    # insert states into spaces, remember numbers as seeds
    self.s = []
    for y in range(self.rows):
      row = []
      for x in range(self.cols):
        state = game.board[y][x]
        space = Space(self, x, y, state)
        row.append(space)
        if space.is_seed():
          self.seeds.append(space)
      self.s.append(row)
    # set neighbors for each space
    [[space.set_neighbors(self) for space in row] for row in self.s]

    # remember how big stream will be at end
    self.target = self.rows * self.cols - sum(map(lambda x: x.state, self.seeds))
  
  # takes a game and updates all the states
  def copy_game(self, game):
    for y in range(self.rows):
      for x in range(self.cols):
        space = self.s[y][x]
        space.state = game.board[y][x]
        space.forget_group()
        space.forget_reachers()
  # returns true if coordinate is upper left of puddle
  def is_puddle(self, (x, y)):
    if x < 0 or x >= self.cols - 1 or y < 0 or y >= self.rows - 1: 
      return False
    return (self.s[y][x].state == WATER and
            self.s[y][x+1].state == WATER and
            self.s[y+1][x].state == WATER and
            self.s[y+1][x+1].state == WATER)
  def get_blanks(self):
    blanks = []
    for row in self.s:
      for space in row:
        if space.state == BLANK:
          blanks.append(space)
    return blanks
  def forget_groups(self):
    for row in self.s:
      for space in row:
        if space.group != None:
          space.forget_group()
  def calculate_groups(self, infer = False):
    for row in self.s:
      for space in row:
        space.find_group(infer)

  # returns a GameState, setting a flag for every square in an invalid group
  def check(self, controller):
    # because nothing else in the system actually uses infer groups, save them only temporarily
    infer_groups = [[None for x in range(self.cols)] for y in range(self.rows)]
    group_dict = {}
    for tipe in Type:
      group_dict[tipe] = []
    group_dict['CROWDED_ISLAND'] = []

    # sweep through seeds to see if any have too many islands
    for seed in self.seeds:
      reg_group = seed.find_group(infer = False)
      if reg_group.type == Type.INVALID_ISLAND:
        # note that this one will have duplicates
        group_dict['CROWDED_ISLAND'].append(reg_group)

    # sweep once to calculate island groups and infer some islands if not marked in game
    for y in range(self.rows):
      for x in range(self.cols):
        space = self.s[y][x]
        if space.state != WATER and not infer_groups[y][x]:
            group = space.find_group(infer = True, remember = False)
            for s in group.spaces + group.dofs:
              infer_groups[s.y][s.x] = group
            group_dict[group.type].append(group)          

    # sweep one more time after guessed spaces have been filled in for water
    water_count = 0
    target_acquired = False
    for y in range(self.rows):
      for x in range(self.cols):
        space = self.s[y][x]
        if space.state == WATER and not infer_groups[y][x]:
            group = space.find_group(infer = True, remember = False)
            for s in group.spaces:
              infer_groups[s.y][s.x] = group
            group_dict[group.type].append(group)
            water_count += 1
            if group.type == Type.CLOSED_WATER and len(group.spaces) == self.target:
              target_acquired = True

    island_error = len(group_dict['INVALID_ISLAND']) or len(group_dict['CROWDED_ISLAND'])
    incomplete = len(group_dict['INCOMPLETE']) or len(group_dict['LONE_BLANK'])
    water_error = len(group_dict['CLOSED_WATER']) or len(group_dict['INVALID_WATER'])

    # if there are no wrong islands and only one water of target length, it's solved
    if not island_error and target_acquired and water_count == 1:
      return GameState.SOLVED
    # if there are no errors and it's still missing stuff, it's okay to continue
    elif not island_error and not water_error and incomplete:
      return GameState.OKAY
    # otherwise, it's wrong. do fancy thing with adding things to flag

    # flag all wrong islands
    for group in set(group_dict['CROWDED_ISLAND']):
      for space in group.spaces:
        controller.flagGame((space.x, space.y), space.state)
    for group in (group_dict['INVALID_ISLAND']):
      for space in group.spaces:
        controller.flagGame((space.x, space.y), space.state)
      for space in group.dofs:
        controller.flagGame((space.x, space.y), space.state)
    # for groups with puddles, find the puddles, and highlight that
    for group in group_dict['INVALID_WATER']:
      to_flag = []
      for corner in group.spaces:
        if self.is_puddle((corner.x, corner.y)):
          x, y = corner.x, corner.y
          to_flag.extend([self.s[y][x], self.s[y+1][x], self.s[y][x+1], self.s[y+1][x+1]])
      for space in set(to_flag):
        controller.flagGame((space.x, space.y), space.state)
    # if it's only wrong because the water's aren't connected, flag all but biggest
    apart = sorted(group_dict['CLOSED_WATER'], key = lambda g: len(g.spaces))
    if water_count > 0 and water_count == len(group_dict['CLOSED_WATER']):
      apart.pop()
    for group in apart:
      for space in group.spaces:
        controller.flagGame((space.x, space.y), space.state)
    return GameState.ERROR

  # what the solver calls to see if it's made a mistake
  # TODO: be able to pass it a region at which to start
  # TODO: repair flagging behavior
  def status(self, region = None):

    # because nothing else in the system actually uses infer groups, save them only temporarily
    infer_groups = [[None for x in range(self.cols)] for y in range(self.rows)]

    for seed in self.seeds:
      if (seed.find_group(infer = False)).type == Type.INVALID_ISLAND:
        return GameState.ERROR

    # sweep once to calculate island groups and infer some islands if not marked in game
    incomplete = False
    for y in range(self.rows):
      for x in range(self.cols):
        space = self.s[y][x]
        if space.state != WATER and not infer_groups[y][x]:
          group = space.find_group(infer = True, remember = False)
          # if it's an invalid island, log an error, and flag it for the solver and controller
          if group.type == Type.INVALID_ISLAND:
            return GameState.ERROR
          elif group.type == Type.INCOMPLETE or group.type == Type.LONE_BLANK:
            incomplete = True
          # remember group in temp array to not run again
          for s in group.spaces + group.dofs:
            infer_groups[s.y][s.x] = group          

    # sweep one more time after guessed spaces have been filled in for water
    target_acquired = False
    water_count = 0
    for y in range(self.rows):
      for x in range(self.cols):
        space = self.s[y][x]
        if space.state == WATER and not infer_groups[y][x]:
          group = space.find_group(infer = True, remember = False)
          water_count += 1

          # if it's an invalid water. i.e. has a puddle, flag
          if group.type == Type.INVALID_WATER:
            return GameState.ERROR

          # if it's a closed water, flag. the solution will be marked as this, so need to remember if its
          # size equals the target
          elif group.type == Type.CLOSED_WATER:
            if len(group.spaces) == self.target:
              target_acquired = True
            else:
              return GameState.ERROR

          for s in group.spaces:
            infer_groups[s.y][s.x] = group

    # if there are no wrong islands and only one water of target length, it's solved
    if target_acquired and water_count == 1:
      return GameState.SOLVED
    # if there are no errors and it's still missing stuff, it's okay to continue
    elif not target_acquired and incomplete:
      return GameState.OKAY
    # otherwise, it's wrong
    else:
      return GameState.ERROR

  # takes a list of spaces and returns a list of all blanks that are bordered by all of them
  def common_blanks(self, spaces):
    length = len(spaces)
    if length == 0:
      return []
    elif length == 1:
      return spaces[0].neighbors
    elif length == 2:
      one, two = [], []
      for n in spaces[0].neighbors:
        if n.state == BLANK:
          one.append(n)
      for n in spaces[1].neighbors:
        if n.state == BLANK:
          two.append(n)
      return set(one) & set(two)
    else:
      return []

  # takes a start and end, and attempts to walk through blanks and infers
  # appends to chains any chain that it finds, where chains only contain blanks
  def chain(self, this, goal, left, used, chains):
    if this == goal:
      chains.append(used[:])
      return
    elif left < this.distance(goal):
      return
    # if it has a neighbor that's another island, can't use as part of chain
    for n in this.neighbors:
      if n.state == ISLAND or n.state > 0:
        return
    # for every neighbor that's a blank or infer chain further
    for n in this.neighbors:
      if n.state == BLANK or n.state == INFER:
        if this.state == BLANK:
          copy = used[:]
          copy.append(this)
          self.chain(n, goal, left - 1, copy, chains)
        else:
          self.chain(n, goal, left - 1, used, chains)

  # fills up reacher lists with seeds that can reach the spaces
  # if it had separated islands it chained together, returns a list of things it knows it must be islands
  def calculate_reachers(self):

    # everything needs a group
    self.calculate_groups()

    must_be_islands = []
    chainer_groups = {}

    # forget reachers for blanks and anonymous islands
    for row in self.s:
      for space in row:
        if space.owner == None:
          space.reachers = []

        # for isolated islands that are owned by seeds, prepare to chain to them
        if space.group != None and space.group.type == Type.LONE_ISLAND and space.owner != None and space.owner.is_seed():
          space.group.numbers = [space.owner]
          if space.owner not in chainer_groups:
            chainer_groups[space.owner] = queue()
            chainer_groups[space.owner].put(space.owner.group)
          chainer_groups[space.owner].put(space.group)
    has_chainers = chainer_groups.keys()

    # takes a group and a search depth, and returns all blanks in reach
    def reaches(group, start_depth):
      # use queue to perform breadth first search
      q = queue()
      can_reach = []
      tagged = []
      for dof in group.dofs:
        q.put((dof, start_depth))
      while not q.empty():
        space, depth = q.get()
        # tag that it's been viewed so it doesn't get searched again
        space.tag = True
        tagged.append(space)

        # if out of depth or already owned, ignore
        if depth <= 0:
          continue
        # skip if it belongs to some other group
        if space.owner != None and space.owner != group.numbers[0]:
          continue
        clash = False
        # crawl to all of its neighbors
        for n in space.neighbors:
          if n.is_island() and n.owner != None and n.owner != group.numbers[0]:
            clash = True            
          elif not n.tag:
            q.put((n, depth - 1))
        # if none of its neighbors are other islands, can reach
        # log a reacher only if it isn't already owned
        if not clash and not space.owner:
          can_reach.append(space)
      # wipe all tags
      for space in tagged:
        space.tag = False
      return can_reach      


    # for every island that doesn't have chainers, log reachers
    for seed in set(self.seeds) - set(has_chainers):
      can_reach = reaches(seed.group, seed.state - len(seed.group.spaces))
      for space in can_reach:
        space.reachers.append(seed)

    # for the seeds with faraway groups... it's complicated
    for seed, groups in chainer_groups.items():      
      num = seed.state
      left = num - len(groups[0].spaces) - len(groups[1].spaces) + 1

      if len(groups) > 2 or left > 6:
        #print 'just giving up trying to chain more than two groups', seed
        can_reach = reaches(seed.group, seed.state - len(seed.group.spaces))
        for space in can_reach:
          space.reachers.append(seed)
        continue

      # change everything in these groups temporarily to infer to differentiate from others
      for space in seed.owns:
        space.state = INFER

      chains = []
      if left <= 6:
        for origin in groups[0].spaces:
          for target in groups[1].spaces:
            self.chain(origin, target, left, [], chains)

      # revert everything back to its original state
      for space in seed.owns:
        space.state = ISLAND
      seed.state = num


      # for each chain, pretend it's a group, find out everything it can reach
      # return the intersection as the actual thing it can reach      
      can_reaches = []
      for chain in chains:
        for space in chain:
          space.state = ISLAND
        group = seed.find_group(infer = False, remember = False)
        can_reach = reaches(group, seed.state - len(group.spaces))
        can_reaches.append(can_reach)
        for space in chain:
          space.state = BLANK
          space.forget_reachers()

      # chains might be empty if something went wrong earlier
      if chains == []:
        can_reach = reaches(seed.group, seed.state - len(seed.group.spaces))
        for space in can_reach:
          space.reachers.append(seed)
        continue      

      # union together the chains and the can_reaches of each chain
      chain_union = set.union(*map(set, chains))
      actually_can_reach = chain_union.union(*map(set, can_reaches))
      for can_reach in actually_can_reach:
        can_reach.reachers.append(seed)

      # all spaces that appear in every chain must be an island
      definite_islands = list(set.intersection(*map(set, chains)))
      must_be_islands.extend(map(lambda isle: (isle, seed), definite_islands))

    return must_be_islands

  def from_good_pairs(self):
    # returns pairs of spaces that are next to two waters and reachable by only one seed
    def good_pair((x, y)):
      waters = []
      blanks = []
      for space in [self.s[y][x], self.s[y][x+1], self.s[y+1][x], self.s[y+1][x+1]]:
        if space.state == WATER:
          waters.append(space)
        elif space.state == BLANK:
          blanks.append(space)
        else:
          return None
      if len(waters) != 2 or len(blanks) != 2:
        return None
      b1, b2 = blanks
      if len(b1.reachers) != 1 or len(b2.reachers) != 1 or b1.reachers[0] != b2.reachers[0]:
        return None
      if b1.x == b2.x or b1.y == b2.y:
        return (b1, b2)
      return None

    must_be_islands = []
    # scan over entire board for good pairs
    for y in range(self.rows - 1):
      for x in range(self.cols - 1):
        res = good_pair((x, y))
        if res:
          seed = res[0].reachers[0]
          group = seed.find_group(infer = False)
          left = seed.state - len(group.spaces) + 1

          # if it's too far, give up
          if left >= 6:
            continue

          # prepare to chain by setting states to infer
          num = seed.state
          for s in seed.owns:
            s.state = INFER
          
          # attempt to chain to both spots
          chain_overlap = []
          for target in [res[0], res[1]]:
            chains = []
            self.chain(seed, target, left, [], chains)
            if len(chains):
              chain_overlap.append(set.intersection(*map(set, chains)))
            else:
              chain_overlap.append(set())

          for s in seed.owns:
            s.state = ISLAND
          seed.state = num

          # spaces are necessarily islands if they appear in all chains or if they appear in
          # each other's chains
          necessary = list(set.intersection(*map(set, chain_overlap)))
          if res[0] in chain_overlap[1]:
            necessary.append(res[0])
          if res[1] in chain_overlap[0]:
            necessary.append(res[1])
          must_be_islands.extend(map(lambda isle: (isle, seed), necessary))

    return must_be_islands

  # here it comes.
  def solve(self, controller = None):
    # change the state of a space, update its owner, add all the neighbors into the queue
    # all changes flow through this function
    def alter(space, state, known_owner = None):
      # queue up this space and all its neighbors
      for n in space.neighbors:
        q.put(n)
      q.put(space)

      # if no changes, don't bother with checking the rest
      if space.state == state and known_owner == space.owner:
        return True

      # if the state should be changed, change it, then forget all nearby groups
      if space.state != state:
        space.state = state
      space.forget_group()
      for n in space.neighbors:
        n.forget_group()

        # if controller is set, let know that it should draw something
        if controller and self.solving:
          controller.queueChange((space.x, space.y), state)

      # if it was given an owner, set it.
      if known_owner != None:
        space.set_owner(known_owner)
      # by convention, water squares own themselves
      elif state == WATER:
        space.set_owner(space)
      # if it's an island, attempt to find an owner, either through its newfound group or its only reacher
      elif state == ISLAND:
        group = space.find_group(infer = False)
        if space.owner == None:
          if group.numbers:
            owner = space.group.numbers[0]
            for this in group.spaces:
              this.set_owner(owner)
          elif len(space.reachers) == 1:
            space.set_owner(space.reachers[0])
      return True

    # TODO: attempt to save groups or something to save computation time on the way back
    def save_game():      
      old = Game(self.rows, self.cols, grid = self)
      return old
    def reset_game(old):
      for y in range(self.rows):
        for x in range(self.cols):
          space = self.s[y][x]
          if space.state != old.board[y][x]:
            space.state = old.board[y][x]
            if controller and self.solving:
              controller.queueChange((x, y), old.board[y][x])          
          space.forget_group()
          space.forget_reachers()

    # clear the queue according to the simpler local rules
    def process():
      while not q.empty():
        if not self.solving:
          return
        this = q.pop()
        global processed_count
        processed_count += 1

        # if water only has one place to go, make stream go there
        if this.state == WATER:
          group = this.find_group(infer = False)
          if len(group.dofs) == 1:
            if len(group.spaces) < self.target:
              alter(group.dofs[0], WATER)

        elif this.is_island():
          group = this.find_group(infer = False)
          if group.type == Type.LONE_ISLAND:
            left = 1
          else:
            left = group.numbers[0].state - len(group.spaces)

          # if island is fully filled in, surround with water
          if left == 0:
            for dof in group.dofs:
              alter(dof, WATER)

          # if island not done yet but only has one dof, make it continue there
          elif len(group.dofs) == 1:
            alter(group.dofs[0], ISLAND)

        # if a space is bordered by two islands, fill in with water
        elif this.state == BLANK:
          shores = []
          for n in this.neighbors:
            if n.is_island() and n.owner != None and n.owner not in shores:
              shores.append(n.owner)
          if len(shores) >= 2:
            alter(this, WATER)

    # apply more complicated rules, returning true if changed
    def process_all():
      changed = True
      while changed and self.status() != GameState.ERROR:
        changed = False
        global loop_count
        loop_count += 1

        # check occasionally finds islands if the water surrounded a right-sized section
        for row in self.s:
          for space in row:
            if space.state == INFER:
              changed = alter(space, ISLAND)

        # calculate reachers, a huge function. it might have found islands
        island_owner_pairs = self.calculate_reachers()
        for isle, owner in island_owner_pairs:
          #print 'found via chain at', isle
          changed = alter(isle, ISLAND, owner)

        # look for spaces that can't be reached by any seed and mark them as water
        for row in self.s:
          for space in row:
            if space.state == BLANK and not space.owner and not space.reachers:
              #print 'can\'t reach', space
              changed = alter(space, WATER)

            # also any lone islands that have just uncovered their owner, change their owner
            elif space.state == ISLAND and not space.owner and len(space.reachers) == 1:
              reacher = space.reachers[0]
              if reacher != space:
                #print 'deduced', reacher, 'owns', space
                changed = alter(space, ISLAND, reacher)
        
        # this will mostly mark edges and things really close to long islands
        process()

        # looks for spaces that would complete puddles and mark them as islands
        antipuddles = []
        for y in range(self.rows):
          for x in range(self.cols):
            space = self.s[y][x]
            if space.state == BLANK:
              space.state = WATER
              if self.is_puddle((x,y)) or self.is_puddle((x,y-1)) or self.is_puddle((x-1,y)) or self.is_puddle((x-1,y-1)):
                antipuddles.append(space)
              space.state = BLANK
        for antipuddle in antipuddles:
          #print 'antipuddle at', antipuddle
          changed = alter(antipuddle, ISLAND)
        
        # for things that must be islands because of the good pairs, change to islands
        island_owner_pairs = self.from_good_pairs()
        for isle, owner in island_owner_pairs:
          changed = alter(isle, ISLAND, owner)
          #print 'via good pair chains at', isle

        # for any island with one space left where both dofs share the same neighbor
        for seed in self.seeds:
          group = seed.find_group(infer = False)
          if seed.state - len(group.spaces) == 1 and len(group.dofs) == 2:
            forks = self.common_blanks(group.dofs)
            for fork in forks:
              #print 'island forks around at', fork
              changed = alter(fork, WATER)

        process()
    
    # scores blanks by how well informative it thinks it'll be in guessing    
    def guess_score(space):
      score = 0.
      for n in space.neighbors:
        if n.state == BLANK:
          score -= 5
      for reacher in space.reachers:
        group = reacher.find_group(infer = False, remember = False)
        left = reacher.state - len(group.spaces)
        score += 10 / max(left, 1)
        score -= space.distance(reacher) * 3
      score += abs(space.x - self.cols / 2) * .5
      score += abs(space.y - self.rows / 2) * .5
      return score

    Guess = Enum(['CONCLUSIVE', 'DEADEND', 'INCONCLUSIVE', 'VICTORY', 'SKIPPED'])

    def guess_single(guessing):
      if not self.solving:
        return Guess.DEADEND
      if guessing.state != BLANK:
        return Guess.SKIPPED

      global guessed_count
      save = save_game()
      by_poe = None

      # choose order of guessing
      if guessing.flag == WATER:
        try1, try2 = ISLAND, WATER
      elif guessing.flag == ISLAND:
        try1, try2 = WATER, ISLAND
      else:
        try1, try2 = ISLAND, WATER

      guessed_count += 1
      reset_game(save)
      alter(guessing, try1)
      process_all()
      #print 'guess', index, 'is', guessing
      status = self.status()
      if status == GameState.SOLVED:
        return Guess.VICTORY
      elif status == GameState.ERROR:
        # remember that it narrowed it down
        by_poe = try2
      else: # elif status == GameState.OKAY:
        other = save_game()

      guessed_count += 1
      reset_game(save)
      alter(guessing, try2)
      process_all()
      #print 'guess', index, 'is', guessing
      status = self.status()
      if status == GameState.SOLVED:
        return Guess.VICTORY
      elif status == GameState.ERROR:
        if by_poe:
          reset_game(save)
          return Guess.DEADEND
        else:
          reset_game(other)
          return Guess.CONCLUSIVE
      else: # elif status == GameState.OKAY:
        if by_poe:
          return Guess.CONCLUSIVE
        else:
          reset_game(save)
          return Guess.INCONCLUSIVE

    # recursively runs through the guessing queue and trying combinations until solved
    # kind of crappy algorithm, really
    def guess_recur(guess_queue, index):
      if not self.solving:
        return False
      global guessed_count
      length = len(guess_queue)
      if length == 0:
        return False

      # find the next blank in the queue
      while guess_queue[index].state != BLANK:
        index += 1
        if index >= length:
          return False                
      guessing = guess_queue[index]
      save = save_game()      

      # choose order of guessing
      if guessing.flag == WATER:
        try1, try2 = ISLAND, WATER
      elif guessing.flag == ISLAND:
        try1, try2 = WATER, ISLAND
      else:
        try1, try2 = ISLAND, WATER

      # guess first try, and progress board
      guessed_count += 1

      # TODO: for some reason, it seemed to bug out without clearing the groups
      reset_game(save)
      alter(guessing, try1)
      process_all()
      #print 'guess', index, 'is', guessing
      #print self
      status = self.status()
      if status == GameState.SOLVED:
        return True
      elif status == GameState.OKAY:
        # if inconclusive, go deeper
        if guess_recur(guess_queue, index + 1):
          return True
      
      if not self.solving:
        return False
      # if it got here, it knows for sure that try1 was wrong
      guessed_count += 1
      reset_game(save)
      alter(guessing, try2)
      process_all()
      #print 'guess', index, 'is', guessing
      #print self
      status = self.status()
      if status == GameState.SOLVED:
        return True
      elif status == GameState.OKAY:
        # since the board has conclusively progressed, remodel the guess queue
        # TODO: for some reason, remodeling the guess queue does not work well, which means the scoring heuristic is shitty
        #new_guess_queue = sorted(self.get_blanks(), key = guess_score, reverse = True)
        #return guess_recur(new_guess_queue, 0, depth - 1)
        return guess_recur(guess_queue, index + 1)
      return False

    # okay, let's actually start doing things now!
    start = time.time()    
    global loop_count, processed_count, grouped_count, guessed_count
    loop_count, processed_count, grouped_count, guessed_count = 0, 0, 0, 0

    # wipe the board of everything
    for row in self.s:
      for space in row:
        if not space.is_seed():
          space.state = BLANK
        space.forget_reachers()
        space.forget_group()
    q = queue()

    # if controller is known, have it update the board to the blank state
    if controller and self.solving:
      for y in range(self.rows):
        for x in range(self.cols):
          controller.queueChange((x, y), self.s[y][x].state)

    # fill queue with seeds, and surround trivially complete seeds with water
    for seed in sorted(self.seeds, key = lambda x: x.state, reverse = True):
      if seed.state == 1:
        for n in seed.neighbors:
          alter(n, WATER)
      else:
        q.put(seed)

    # naively traverse board and if surrounded by two seeds, color and put in queue
    for row in self.s:
      for space in row:
        if sum(map(lambda s: s.is_seed(), space.neighbors)) >= 2:
          alter(space, WATER)

    # do naive processing. actually solves the entire thing for many small boards
    process()

    # apply all heuristics it has, looping over the different ones until no changes are made
    process_all()

   # print out the reacher map
    if not controller:
      #print '\n'.join(' '.join(str(len(s.reachers)) if s.owner == None else '.' for s in row) for row in self.s) + '\n'  
      print 'took', str(round(time.time() - start, 3)), 'seconds,', loop_count, 'loops,', 
      print processed_count, 'processed,', grouped_count, 'groups,', len(self.get_blanks()), 'to guess'
    
    changed_count = 1
    while changed_count > 0:
      if not controller:
        print self
      changed_count = 0
      guess_queue = sorted(self.get_blanks(), key = guess_score, reverse = True)
      for guessing in guess_queue:
        res = guess_single(guessing)
        if res == Guess.INCONCLUSIVE:
          res = 'aww'
        elif res == Guess.CONCLUSIVE:
          changed_count += 1
        elif res == Guess.SKIPPED:
          res = '...'
        elif res == Guess.VICTORY:
          changed_count = 0
          break
        if not controller:
          print "#" + str(guessed_count), guessing, res
        if res == Guess.DEADEND:
          if controller:
            controller.status = self.status()
            controller.stopSolveGame(self.solving)
          return

    # generate the guess tree, which will keep on branching until it solves the game
    final_queue = sorted(self.get_blanks(), key = guess_score, reverse = True)
    if final_queue:
      if not controller:
        print 'resorting to recursive guessing'
      guess_recur(final_queue, 0)

    if not controller:
      print 'took', str(round(time.time() - start, 3)), 'seconds,', loop_count, 'loops,', 
      print processed_count, 'processed,', grouped_count, 'groups,', guessed_count, 'guesses'
      print self
      print self.status()
    if controller:
      controller.status = self.status()
      controller.stopSolveGame(self.solving)

class Space(object):
  def __str__(self):
    return '(' + str(self.x) + ',' + str(self.y) + '): ' + str(self.state)
  def __repr__(self):
    return str(self)
  def __init__(self, grid, x, y, state):
    self.grid = grid
    self.x = x
    self.y = y
    self.neighbors = []
    self.tag = False
    self.flag = None
    self.state = state
    self.group = None
    if state > 0:
      self.reachers = None
      self.owner = self
      self.owns = [self]
    else:
      self.reachers = []
      self.owner = None
      self.owns = []
  def set_neighbors(self, grid):
    x, y = self.x, self.y
    if x > 0:
      self.neighbors.append(grid.s[y][x-1])
    if y < grid.rows - 1:
      self.neighbors.append(grid.s[y+1][x])
    if x < grid.cols - 1:
      self.neighbors.append(grid.s[y][x+1])
    if y > 0:
      self.neighbors.append(grid.s[y-1][x])

  def is_seed(self):
    return self.state > 0
  def is_island(self):
    return self.state > 0 or self.state == ISLAND
  def distance(self, other):
    return abs(self.x - other.x) + abs(self.y - other.y)
  def set_owner(self, owner):
    self.owner = owner
    self.reachers = None
    owner.owns.append(self)

  # hefty function that crawls through neighbors and finding spaces, dofs, and walls
  # if infer is true, will crawl through spaces as well in case player didn't mark them. used in checking
  # if remember is false, will not save any persistent info but will return the proper group instead
  def find_group(self, infer = False, remember = True):
    # circumvent and return already found group and on infer mode
    if remember == True and self.group != None and self.group.inferred == infer:
      return self.group
    # if off infer mode, a blank has no group
    if not infer and self.state == BLANK:
      return self.group

    global grouped_count
    grouped_count += 1
    group = Group()
    group.inferred = infer
    crawl_queue = queue()

    # for a stream group
    if self.state == WATER:
      group.spaces.append(self)
      crawl_queue.put(self)
      self.tag = True

      # crawl through adjacent water spaces, listing walls and dofs
      while not crawl_queue.empty():
        space = crawl_queue.get()
        for n in space.neighbors:
          if n.tag:
            continue
          n.tag = True
          if n.state == WATER:
            group.spaces.append(n)
            crawl_queue.put(n)
          elif n.state == BLANK:
            group.dofs.append(n)
          else:
            group.walls.append(n)

      group.type = Type.WATER
      if len(group.dofs) == 0:
        group.type = Type.CLOSED_WATER
      for space in group.spaces:
        if self.grid.is_puddle((space.x, space.y)):
          group.type = Type.INVALID_WATER
          break
                
    # for an island group
    else:
      if self.is_seed():
        group.numbers.append(self)
      if self.state == BLANK:
        group.dofs.append(self)
      else:
        group.spaces.append(self)
      crawl_queue.put(self)
      self.tag = True

      # crawl through adjacent island marks
      while not crawl_queue.empty():
        space = crawl_queue.get()
        for n in space.neighbors:
          if n.tag:
            continue
          n.tag = True
          if n.state == WATER:
            group.walls.append(n)
          elif n.is_seed():
            group.spaces.append(n)
            crawl_queue.put(n)
            group.numbers.append(n)
          elif n.state == ISLAND:
            group.spaces.append(n)
            crawl_queue.put(n)
          else:
            group.dofs.append(n)
            # if on infer mode, also crawl through spaces
            if infer:
              crawl_queue.put(n)

      # if not on infer, make sure everyone knows their owner
      if not infer and remember:
        for space in group.spaces:
          if space.owner != None and space.owner.is_seed():
            for s in group.spaces:
              if s.owner != space.owner:
                s.set_owner(space.owner)
            break

      # figure out the type of group
      if infer:
        size = len(group.dofs) + len(group.spaces)
      else:
        size = len(group.spaces)
      seed_num = len(group.numbers)      
      # if no number but has islands
      if seed_num == 0:
        # is a lone island. if on infer, then has no numbers connectable, so invalid
        if len(group.spaces) > 0:
          if infer:
            group.type = Type.INVALID_ISLAND
          else:
            group.type = Type.LONE_ISLAND
        else:
          group.type = Type.LONE_BLANK      
      elif seed_num > 1:
        # if too few spaces for seeds, is invalid
        if not infer:
          group.type = Type.INVALID_ISLAND
        elif sum(map(lambda x: x.state, group.numbers)) + 1 > size:
          group.type = Type.INVALID_ISLAND
        # otherwise, conclude it's a not yet played
        else:
          group.type = Type.INCOMPLETE
      else:
        num = group.numbers[0].state
        # if it's possible for group to be a valid island
        if len(group.spaces) > num:
          group.type = Type.INVALID_ISLAND
        elif size == num:
        # if on infer, mark blanks as part of island
          if infer:
            for dof in group.dofs:            
              dof.state = INFER
            group.spaces.extend(group.dofs)
            group.dofs = []
          group.type = Type.ISLAND
        elif size > num:
          group.type = Type.INCOMPLETE
        # if too few blanks, mark as wrong
        else:
          if infer:
            group.type = Type.INVALID_ISLAND
          else:
            group.type = Type.INCOMPLETE

      
    # wipe tags for next time's use, and point members of group to group
    for dof in group.dofs:
      dof.tag = False
      if remember and self.state != WATER and infer:
        dof.group = group
    for wall in group.walls:
      wall.tag = False
    for space in group.spaces:
      space.tag = False
      if remember:
        space.group = group

    return group

  # forces all spaces that are pointed to this group to lose their pointer
  def forget_group(self):
    if self.group == None:
      return
    group = self.group
    for space in group.spaces:
      space.group = None
    if group.type != Type.WATER and group.type != Type.INVALID_WATER:
      for dof in group.dofs:
        dof.group = None
  # forgets reacher connections
  def forget_reachers(self):
    if self.is_seed():
      for space in self.owns:
        space.owner = None
        space.reachers = []
        space.owns = []
      self.reachers = None
      self.owner = self
      self.owns = [self]
    else:
      self.reachers = []
      self.owner = None
      for space in self.owns:
        space.owner = None
        space.reachers = []
        space.owns = []
      self.owns = []

# holder for lists of spaces, dofs, walls, numbers, and type
class Group(object):
  def __str__(self):
    dofs_str = str(len(self.dofs)) + ' dofs: ' + str(self.dofs)
    walls_str = str(len(self.walls)) + ' walls: ' + str(self.walls)
    spaces_str = str(len(self.spaces)) + ' spaces: ' + str(self.spaces)    
    return str(self.type) + ':\n' + spaces_str + '\n' +  walls_str +'\n' + dofs_str + '\n'
  def __rcutepr__(self):
    return str(self)
  def __init__(self):
    self.spaces = []
    self.dofs = []
    self.walls = []
    self.numbers = []
    self.type = Type.INCOMPLETE

# a list that pushes, pops, and enforces uniqueness
class queue(list):
  def put(self, elt):
    if elt not in self:
      self.append(elt)
  def cut(self, elt):
    if elt not in self:
      self.insert(0, elt)
  def empty(self):
    return not self
  def get(self):
    return self.pop(0)
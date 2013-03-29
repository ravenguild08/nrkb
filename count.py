import nrkb_fctrl
import time
for size in [5, 7, 10, 12, 15, 20]:
  print 'there are', nrkb_fctrl.num_boards(size), 'boards for', str(size) + 'x' + str(size)
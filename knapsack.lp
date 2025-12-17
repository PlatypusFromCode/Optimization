\ Model knapsack
\ LP format - for model browsing. Use MPS format to capture full model detail.
\ Signature: 0x36bab8b8429b0032
Maximize
  10 x[0] + 13 x[1] + 7 x[2] + 18 x[3] + 12 x[4] + 9 x[5] + 14 x[6] + 6 x[7]
   + 16 x[8] + 11 x[9]
Subject To
 capacity: 2 x[0] + 3 x[1] + 2 x[2] + 5 x[3] + 3 x[4] + 2 x[5] + 4 x[6]
   + x[7] + 5 x[8] + 3 x[9] <= 12
Bounds
Binaries
 x[0] x[1] x[2] x[3] x[4] x[5] x[6] x[7] x[8] x[9]
End

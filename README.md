GOAL:
Take an existing project (my Capstone circuit, see REFERENCES below) and utilize GitHub actions / Namespace to:
 - Perform ERC (Electrical Rule Check) validation
 - Export netlist / BOM
 - Simulate 27 corners + 2000-run Monte Carlo (ngspice)
 - Export sim results

RESULTS:
Three comparisons were created:
|                                                  Stats |          GitHub (unoptimized) |       Namespace (unoptimized) |  right vs left
run id                                             |     42330906243 |     42330906329 |
commit                                             |         bfe4377 |         bfe4377 |
status                                             |         success |         success |
TOTAL wall-clock (first job start -> last job end) | 375 s (6.2 min) | 147 s (2.5 min) |   2.55x faster
TOTAL queue before first job                       |             2 s |             8 s |   4.00x slower
TOTAL runner time (sum of all jobs)                | 371 s (6.2 min) | 145 s (2.4 min) |   2.56x faster
TOTAL jobs                                         |               3 |               3 |
job  erc: wall                                     |            31 s |             8 s |   3.88x faster
job  export: wall                                  |            29 s |            23 s |   1.26x faster
job  sim: wall                                     | 311 s (5.2 min) |           114 s |   2.73x faster



|        Stats                                           |          GitHub (optimized, nocache) |       Namespace (optimized, nocache) |  right vs left
run id                                             |     42402137024 |     42402137008 |
commit                                             |         2ada952 |         2ada952 |
status                                             |         success |         success |
TOTAL wall-clock (first job start -> last job end) | 538 s (9.0 min) | 181 s (3.0 min) |   2.97x faster
TOTAL queue before first job                       |             2 s |             8 s |   4.00x slower
TOTAL runner time (sum of all jobs)                | 533 s (8.9 min) | 178 s (3.0 min) |   2.99x faster
TOTAL jobs                                         |               4 |               4 |
job  image: wall                                   | 146 s (2.4 min) |            61 s |   2.39x faster
job  erc: wall                                     |            33 s |            18 s |   1.83x faster
job  export: wall                                  |            43 s |            17 s |   2.53x faster
job  sim: wall                                     | 311 s (5.2 min) |            82 s |   3.79x faster


DOCKER IMAGE ( cache )

|                Stats                                   |          GitHub (optimized, warm-cache) |       Namespace (optimized, warm-cache) |  right vs left
run id                                             |     42403222071 |     42403222193 |
commit                                             |         2305f19 |         2305f19 |
status                                             |         success |         success |
TOTAL wall-clock (first job start -> last job end) | 338 s (5.6 min) |           111 s |   3.05x faster
TOTAL queue before first job                       |             3 s |             2 s |   1.50x faster
TOTAL runner time (sum of all jobs)                | 332 s (5.5 min) |           108 s |   3.07x faster
TOTAL jobs                                         |               4 |               4 |
job  image: wall                                   |            17 s |            13 s |   1.31x faster
job  erc: wall                                     |            35 s |             7 s |   5.00x faster
job  export: wall                                  |            43 s |             9 s |   4.78x faster
job  sim: wall                                     | 237 s (4.0 min) |            79 s |   3.00x faster





REFERENCES:
Our Blueprint report for the Electrome project (schematic simulated in this project):
[Listen to Plants: A Multichannel Electrical Sensing Platform for Plant Physiology](docs/Blueprint.pdf)

Description of a Capstone project:
[CAPSTONE project description](https://smithengineering.queensu.ca/ece/undergraduate/courses/elec-498.html)

[ngspice Documentation](https://ngspice.sourceforge.io/)


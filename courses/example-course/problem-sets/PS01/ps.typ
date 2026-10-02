// Example problem set: `student` mode hides the solutions, `solutions` mode shows them.
#import "/themes/karthein-notes.typ": *

#show: notes.with(
  course: "PHYS 206",
  kind: "Problem Set",
  number: 1,
  title: [One-Dimensional Motion],
  date: "Due 2027-01-26",
  author: "Your Name",
  alts: yaml("ps.alts.yaml"),
)

Show your reasoning: a diagram, the equation you start from, the algebra, then the number
with its unit. Take $g = 9.8 "m/s"^2$.

#problem(points: 10, title: [Reading a graph])[
  A position-time graph shows a straight line from $(0 "s", 2 "m")$ to $(4 "s", -6 "m")$.
  What is the velocity, and what is the displacement over the four seconds?
  #solution[
    The slope is the velocity (fractions go in display math; inline they shrink to stacked type):
    $ v = (-6 "m" - 2 "m") / (4 "s") = -2 "m/s". $
    The displacement is $Delta x = -8 "m"$; the distance travelled is 8 m.
  ]
]

#problem(points: 15, title: [Stopping distance])[
  A car travelling at $30 "m/s"$ brakes with a constant deceleration of $6 "m/s"^2$. How
  far does it travel before stopping, and how long does it take?
  #solution[
    With $v = 0$:
    $ x - x_0 = v_0^2 / (2 a) = (30 "m/s")^2 / (2 times 6 "m/s"^2) = 75 "m", quad t = v_0 / a = 5 "s". $
  ]
]

#problem(points: 15, title: [Two trains])[
  Two trains on the same track head toward each other, one at $20 "m/s"$, the other at
  $15 "m/s"$, 700 m apart. Each driver sees the other and brakes at $1.0 "m/s"^2$. Do they
  collide? Support your answer with a calculation, not a feeling.
  #solution[
    Stopping distances $v_0^2 \/ (2 a)$: $200 "m"$ and $112.5 "m"$, together 312.5 m, less than
    700 m. No collision; they stop 387.5 m apart.
  ]
]

// Example lecture on the notes theme: compiles in all three modes.
//   typst compile --root . --pdf-standard ua-1 --input mode=student courses/example-course/lectures/L01-kinematics/notes.typ
//   typst compile --root . --pdf-standard ua-1 --input mode=lecture ... (empty space where `work` and `blank` are)
//   typst compile --root . --features html --format html --input mode=student ... (MathML equations)
// Equation alt text: `talks alts courses/example-course/lectures/L01-kinematics/notes.typ`
// writes notes.alts.yaml (spoken drafts); review it, the theme applies it.
#import "/themes/karthein-notes.typ": *

#show: notes.with(
  course: "PHYS 206",
  kind: "Lecture",
  number: 1,
  title: [Motion in One Dimension],
  date: "2027-01-19",
  author: "Your Name",
  alts: yaml("notes.alts.yaml"),
)

= Where Things Are and How Fast They Get There

Mechanics starts with a simple question: *where is the object, and when?* Everything in this
chapter follows from writing the answer as a function $x(t)$ and asking how it changes.

#definition(title: [Position, displacement, distance])[
  The *position* $x$ is a coordinate along a chosen axis, with a chosen origin and a chosen
  positive direction. The *displacement* between two instants is the change in position,
  $Delta x = x_2 - x_1$; it can be negative. The *distance* travelled is the length of the
  path and is never negative.
]

#two-col[
  Average velocity is displacement per time,
  #eq(numbered: true)[$ v_"avg" = (Delta x)/(Delta t) = (x_2 - x_1)/(t_2 - t_1). $]
  Shrinking the interval gives the instantaneous velocity, the slope of the $x(t)$ curve:
  #eq(numbered: true)[$ v = lim_(Delta t -> 0) (Delta x)/(Delta t) = (dif x)/(dif t). $]
][
  #cat-fig("plot-us-cpi-u-yoy-2023-2026", width: 100%, caption: [A placeholder plot from the catalog: any catalogued figure can stand here with its alt text.])
]

#concept[
  Velocity is the *slope* of position against time; acceleration is the slope of velocity
  against time. Reading slopes off a graph is the skill this week trains.
]

== Constant Acceleration

If the acceleration $a$ is constant, integrating twice gives the two equations that carry
most of the chapter:
#eq(numbered: true)[$ v(t) = v_0 + a t, $]
#eq(numbered: true)[$ x(t) = x_0 + v_0 t + 1/2 a t^2. $]
Eliminating $t$ between them gives $v^2 = v_0^2 + 2 a (x - x_0)$, useful whenever the time is
not asked for.

#example(title: [A ball thrown straight up])[
  A ball leaves your hand at $v_0 = 12 "m/s"$ upward. How high does it rise, and how long
  until it is back in your hand? Take $g = 9.8 "m/s"^2$ and the upward direction as positive.
  #work(height: 7cm)[
    At the top $v = 0$, so from $v^2 = v_0^2 - 2 g h$:
    $ h = v_0^2 / (2 g) = (12 "m/s")^2 / (2 times 9.8 "m/s"^2) = 7.3 "m". $
    The flight is symmetric: the time up equals the time down, $t_"up" = v_0 \/ g = 1.22 "s"$,
    so the ball returns after $2 t_"up" = 2.4 "s"$.
  ]
]

#caution(title: [Negative does not mean slowing down])[
  A negative acceleration speeds the object up when it moves in the negative direction. Ask
  whether $v$ and $a$ have the *same sign* (speeding up) or *opposite signs* (slowing down).
]

#checkpoint[
  A car's velocity goes from $-20 "m/s"$ to $-10 "m/s"$ in 2 s. Is it speeding up or slowing
  down, and what is its acceleration?
  #solution[
    The speed falls from 20 to 10 m/s, so it slows down; $a = (Delta v)/(Delta t) = (10 "m/s") / (2 "s") = +5 "m/s"^2$,
    opposite in sign to $v$.
  ]
]

#blank(height: 5cm)

#summary[
  - Position $x(t)$ is the whole story; velocity and acceleration are its first and second slopes.
  - For constant $a$: $v = v_0 + a t$ and $x = x_0 + v_0 t + 1/2 a t^2$; eliminate $t$ with $v^2 = v_0^2 + 2 a Delta x$.
  - Signs carry direction. Same sign of $v$ and $a$: speeding up.
]

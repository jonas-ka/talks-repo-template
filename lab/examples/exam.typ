// Exam theme example (exam mode by default; --input mode=solutions for solutions and rubric).
// The content is a neutral two-problem example; real exams live in the course repositories.
#import "/themes/karthein-exam.typ": *

#show: exam.with(
  course: "PHYS-206-DP",
  term: "Spring 2027",
  title: "Example Exam",
  instructor: "Prof. Karthein",
  sections: "500-505",
  date: "January 1, 10:00 am – 10:50 am",
  equations: eq-sheet(
    left: [
      #eq-group([Kinematics])[
        $v = (dif x)/(dif t)$ and $a = (dif v)/(dif t)$ \
        Constant $a$: $x(t) = x(0) + v(0) t + 1/2 a t^2$
      ]
      #eq-group([Geometry])[
        Surface of a circle: $S = pi r^2$
      ]
    ],
    right: [
      #eq-group([Dynamics])[
        $arrow(F) = m arrow(a)$ \
        $|arrow(f)| <= mu |arrow(N)|$
      ]
    ],
  ),
  alts: yaml("exam.alts.yaml"),
)

#problem(title: [A Ball Thrown Upward])[
  A ball is thrown straight up with speed $v(0)$ from the ground. Ignore air resistance.
]
#part(points: 3, space: 4cm)[Find the time $T$ at which it reaches its highest point. *Show all intermediate steps.*][
  $v(t) = v(0) - g t$ #pts(1)[law] ; at the top $v(T) = 0$ #pts(1)[condition] $=> T = v(0) \/ g$ #pts(1)[result]
]
#part(points: 2, space: 3cm)[Find the maximum height $H$.][
  $H = v(0) T - 1/2 g T^2 = v(0)^2 \/ (2 g)$ #pts(2)[substitution and result]
]

#problem(title: [A Block on a Table])[
  A block of mass $m$ rests on a horizontal table with friction coefficient $mu$.
]
#part(points: 5, space: 5cm, figure: rect(width: 100%, height: 2.2cm, stroke: 0.6pt)[#align(center + horizon)[block on a table]])[
  Draw the free-body diagram and find the largest horizontal push $P$ for which the block stays at rest.
  _No points will be given for this problem if the drawing is skipped._
][
  Forces: $m g$ down, $|arrow(N)|$ up, $P$ and friction horizontal #pts(2)[diagram];
  $|arrow(N)| = m g$ #pts(1)[] , $P <= mu |arrow(N)| = mu m g$ #pts(2)[law and result]
]

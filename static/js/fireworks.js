 var confetti = {
            maxCount: 150,
            speed: 2,
            frameInterval: 15,
            alpha: 1,
            gradient: !1,
            start: null,
            stop: null,
            toggle: null,
            pause: null,
            resume: null,
            togglePause: null,
            remove: null,
            isPaused: null,
            isRunning: null
        };
        ! function () {
            confetti.start = s, confetti.stop = w, confetti.toggle = function () {
                e ? w() : s()
            }, confetti.pause = u, confetti.resume = m, confetti.togglePause = function () {
                i ? m() : u()
            }, confetti.isPaused = function () {
                return i
            }, confetti.remove = function () {
                stop(), i = !1, a = []
            }, confetti.isRunning = function () {
                return e
            };
            var t = window.requestAnimationFrame || window.webkitRequestAnimationFrame || window
                .mozRequestAnimationFrame || window.oRequestAnimationFrame || window.msRequestAnimationFrame,
                n = ["rgba(30,144,255,", "rgba(107,142,35,", "rgba(255,215,0,", "rgba(255,192,203,", "rgba(106,90,205,",
                    "rgba(173,216,230,", "rgba(238,130,238,", "rgba(152,251,152,", "rgba(70,130,180,",
                    "rgba(244,164,96,", "rgba(210,105,30,", "rgba(220,20,60,"
                ],
                e = !1,
                i = !1,
                o = Date.now(),
                a = [],
                r = 0,
                l = null;

            function d(t, e, i) {
                return t.color = n[Math.random() * n.length | 0] + (confetti.alpha + ")"), t.color2 = n[Math.random() *
                        n.length | 0] + (confetti.alpha + ")"), t.x = Math.random() * e, t.y = Math.random() * i - i, t
                    .diameter = 10 * Math.random() + 5, t.tilt = 10 * Math.random() - 10, t.tiltAngleIncrement = .07 *
                    Math.random() + .05, t.tiltAngle = Math.random() * Math.PI, t
            }

            function u() {
                i = !0
            }

            function m() {
                i = !1, c()
            }

            function c() {
                if (!i)
                    if (0 === a.length) l.clearRect(0, 0, window.innerWidth, window.innerHeight), null;
                    else {
                        var n = Date.now(),
                            u = n - o;
                        (!t || u > confetti.frameInterval) && (l.clearRect(0, 0, window.innerWidth, window.innerHeight),
                            function () {
                                var t, n = window.innerWidth,
                                    i = window.innerHeight;
                                r += .01;
                                for (var o = 0; o < a.length; o++) t = a[o], !e && t.y < -15 ? t.y = i + 100 : (t
                                    .tiltAngle += t.tiltAngleIncrement, t.x += Math.sin(r) - .5, t.y += .5 * (Math
                                        .cos(r) + t.diameter + confetti.speed), t.tilt = 15 * Math.sin(t.tiltAngle)
                                ), (t.x > n + 20 || t.x < -20 || t.y > i) && (e && a.length <= confetti
                                    .maxCount ? d(t, n, i) : (a.splice(o, 1), o--))
                            }(),
                            function (t) {
                                for (var n, e, i, o, r = 0; r < a.length; r++) {
                                    if (n = a[r], t.beginPath(), t.lineWidth = n.diameter, i = n.x + n.tilt, e = i + n
                                        .diameter / 2, o = n.y + n.tilt + n.diameter / 2, confetti.gradient) {
                                        var l = t.createLinearGradient(e, n.y, i, o);
                                        l.addColorStop("0", n.color), l.addColorStop("1.0", n.color2), t.strokeStyle = l
                                    } else t.strokeStyle = n.color;
                                    t.moveTo(e, n.y), t.lineTo(i, o), t.stroke()
                                }
                            }(l), o = n - u % confetti.frameInterval), requestAnimationFrame(c)
                    }
            }

            function s(t, n, o) {
                var r = window.innerWidth,
                    u = window.innerHeight;
                window.requestAnimationFrame = window.requestAnimationFrame || window.webkitRequestAnimationFrame ||
                    window.mozRequestAnimationFrame || window.oRequestAnimationFrame || window
                    .msRequestAnimationFrame || function (t) {
                        return window.setTimeout(t, confetti.frameInterval)
                    };
                var m = document.getElementById("confetti-canvas");
                null === m ? ((m = document.createElement("canvas")).setAttribute("id", "confetti-canvas"), m
                    .setAttribute("style", "display:block;z-index:999999;pointer-events:none;position:fixed;top:0"),
                    document.body.prepend(m), m.width = r, m.height = u, window.addEventListener("resize",
                        function () {
                            m.width = window.innerWidth, m.height = window.innerHeight
                        }, !0), l = m.getContext("2d")) : null === l && (l = m.getContext("2d"));
                var s = confetti.maxCount;
                if (n)
                    if (o)
                        if (n == o) s = a.length + o;
                        else {
                            if (n > o) {
                                var f = n;
                                n = o, o = f
                            }
                            s = a.length + (Math.random() * (o - n) + n | 0)
                        }
                else s = a.length + n;
                else o && (s = a.length + o);
                for (; a.length < s;) a.push(d({}, r, u));
                e = !0, i = !1, c(), t && window.setTimeout(w, t)
            }

            function w() {
                e = !1
            }
        }();

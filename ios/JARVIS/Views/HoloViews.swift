import Speech
import SwiftUI

// El aspecto holográfico de JARVIS, el mismo que el panel de la tablet: el
// núcleo animado, el fondo, las tarjetas con esquinas cortadas y el arranque.

// MARK: - Núcleo

/// El núcleo de JARVIS, dibujado en tiempo real. En reposo gira despacio en
/// cian; escuchando se vuelve ámbar y lanza ondas; pensando acelera; hablando,
/// el anillo de onda sigue el volumen real de su voz.
struct HoloCoreView: View {
    let phase: ConversationModel.Phase
    var showLabel = true
    var level: () -> Double = { VoicePlayer.shared.level() }

    @State private var state = CoreState()

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, size in
                state.advance(to: timeline.date.timeIntervalSinceReferenceDate, phase: phase, level: level)
                state.draw(in: &context, size: size, phase: phase, showLabel: showLabel)
            }
        }
        .accessibilityHidden(true)
    }
}

/// Lo que el núcleo recuerda entre fotogramas (giro acumulado, color, volumen).
private final class CoreState {
    private struct Particle { var radius: Double; var angle: Double; var speed: Double; var size: Double; var twinkle: Double }
    private typealias RGB = (r: Double, g: Double, b: Double)

    private var last: Double?
    private var time: Double = 0
    private var spin: Double = 0
    private var smoothLevel: Double = 0
    private var main: RGB = (0.145, 0.784, 0.949)
    private var hot: RGB = (0.749, 0.953, 1.0)
    private var particles: [Particle] = (0..<56).map { _ in
        Particle(radius: .random(in: 0.35...0.97), angle: .random(in: 0...(2 * .pi)),
                 speed: .random(in: 0.04...0.22) * (Bool.random() ? 1 : -1),
                 size: .random(in: 0.6...2.0), twinkle: .random(in: 0...(2 * .pi)))
    }

    private static func palette(_ phase: ConversationModel.Phase) -> (RGB, RGB) {
        switch phase {
        case .listening: return ((1.0, 0.710, 0.278), (1.0, 0.910, 0.745))
        case .thinking: return ((0.145, 0.784, 0.949), (1.0, 1.0, 1.0))
        case .idle, .speaking: return ((0.145, 0.784, 0.949), (0.800, 0.970, 1.0))
        }
    }

    private static func speed(_ phase: ConversationModel.Phase) -> Double {
        switch phase {
        case .idle: return 1
        case .listening: return 1.6
        case .thinking: return 4.2
        case .speaking: return 1.4
        }
    }

    private static func label(_ phase: ConversationModel.Phase) -> String {
        switch phase {
        case .idle: return "SISTEMAS EN LÍNEA"
        case .listening: return "ESCUCHANDO"
        case .thinking: return "PROCESANDO"
        case .speaking: return "TRANSMITIENDO"
        }
    }

    func advance(to now: Double, phase: ConversationModel.Phase, level: () -> Double) {
        let dt = min(0.05, max(0, now - (last ?? now)))
        last = now
        time += dt
        spin += dt * Self.speed(phase)
        // Los colores cambian suavemente de un estado a otro.
        let (targetMain, targetHot) = Self.palette(phase)
        let k = min(1, dt * 4)
        main = (main.r + (targetMain.r - main.r) * k, main.g + (targetMain.g - main.g) * k, main.b + (targetMain.b - main.b) * k)
        hot = (hot.r + (targetHot.r - hot.r) * k, hot.g + (targetHot.g - hot.g) * k, hot.b + (targetHot.b - hot.b) * k)
        let raw: Double
        switch phase {
        case .speaking: raw = level()
        case .listening: raw = 0.35 + 0.25 * sin(time * 5)
        default: raw = 0
        }
        smoothLevel += (raw - smoothLevel) * min(1, dt * 12)
        for i in particles.indices {
            particles[i].angle += particles[i].speed * dt * Self.speed(phase)
        }
    }

    private func color(_ c: RGB, _ alpha: Double) -> Color {
        Color(red: c.r, green: c.g, blue: c.b).opacity(alpha)
    }

    func draw(in context: inout GraphicsContext, size: CGSize, phase: ConversationModel.Phase, showLabel: Bool) {
        let cx = Double(size.width) / 2
        let cy = Double(size.height) / 2
        let center = CGPoint(x: cx, y: cy)
        let R = Double(min(size.width, size.height)) / 2 * 0.94
        let t = time
        context.blendMode = .plusLighter

        func point(_ angle: Double, _ radius: Double) -> CGPoint {
            CGPoint(x: cx + cos(angle) * radius, y: cy + sin(angle) * radius)
        }
        func arc(_ radius: Double, _ start: Double, _ length: Double, _ width: Double, _ alpha: Double,
                 _ c: RGB? = nil, dash: [CGFloat] = []) {
            var path = Path()
            path.addArc(center: center, radius: CGFloat(radius), startAngle: .radians(start),
                        endAngle: .radians(start + length), clockwise: false)
            context.stroke(path, with: .color(color(c ?? main, alpha)),
                           style: StrokeStyle(lineWidth: CGFloat(width), lineCap: dash.isEmpty ? .round : .butt, dash: dash))
        }

        // Halo de fondo
        let halo = Path(ellipseIn: CGRect(x: cx - R, y: cy - R, width: R * 2, height: R * 2))
        context.fill(halo, with: .radialGradient(
            Gradient(stops: [.init(color: color(main, 0.20 + smoothLevel * 0.2), location: 0),
                             .init(color: color(main, 0.06), location: 0.45),
                             .init(color: color(main, 0), location: 1)]),
            center: center, startRadius: CGFloat(R * 0.05), endRadius: CGFloat(R)))

        // Escala exterior: marcas cada 3°, más largas cada 15°
        var shortTicks = Path()
        var longTicks = Path()
        for i in 0..<120 {
            let a = Double(i) / 120 * 2 * .pi + spin * 0.05
            let long = i % 5 == 0
            let p1 = point(a, R * 0.965)
            let p2 = point(a, R * (long ? 0.915 : 0.94))
            if long { longTicks.move(to: p1); longTicks.addLine(to: p2) } else { shortTicks.move(to: p1); shortTicks.addLine(to: p2) }
        }
        context.stroke(shortTicks, with: .color(color(main, 0.22)), lineWidth: 1)
        context.stroke(longTicks, with: .color(color(main, 0.55)), lineWidth: 1.4)

        // Anillo segmentado (gira a derechas)
        let segments = 14
        for i in 0..<segments {
            let start = spin * 0.22 + Double(i) / Double(segments) * 2 * .pi
            arc(R * 0.86, start, 2 * .pi / Double(segments) * 0.72, R * 0.035, i % 4 == 0 ? 0.85 : 0.45)
        }

        // Anillo discontinuo (a izquierdas)
        arc(R * 0.775, -spin * 0.35, 2 * .pi, 1.4, 0.55, dash: [2, 7])

        // Tres arcos largos que giran rápido
        for i in 0..<3 {
            let start = spin * 0.9 + Double(i) * 2 * .pi / 3
            arc(R * 0.70, start, .pi * 0.42, 7, 0.10)
            arc(R * 0.70, start, .pi * 0.42, 2.2, 0.8, hot)
        }

        // Barrido de radar
        let sweepAngle = spin * 1.1
        var wedge = Path()
        wedge.move(to: center)
        wedge.addArc(center: center, radius: CGFloat(R * 0.66), startAngle: .radians(sweepAngle - 0.35),
                     endAngle: .radians(sweepAngle), clockwise: false)
        wedge.closeSubpath()
        context.fill(wedge, with: .linearGradient(
            Gradient(colors: [color(main, 0), color(main, 0.24)]),
            startPoint: point(sweepAngle - 0.35, R * 0.4), endPoint: point(sweepAngle, R * 0.4)))

        // Anillo de onda: sigue la voz de JARVIS
        let waveRadius = R * 0.52
        let amplitude = R * (0.012 + smoothLevel * 0.11)
        var wave = Path()
        for i in 0...160 {
            let a = Double(i) / 160 * 2 * .pi
            let n = sin(a * 6 + t * 3.1) * 0.55 + sin(a * 11 - t * 4.7) * 0.3 + sin(a * 17 + t * 2.3) * 0.15
            let p = point(a, waveRadius + n * amplitude)
            if i == 0 { wave.move(to: p) } else { wave.addLine(to: p) }
        }
        wave.closeSubpath()
        context.stroke(wave, with: .color(color(main, 0.35)), lineWidth: 5)
        context.stroke(wave, with: .color(color(hot, 0.9)), lineWidth: 1.6)

        // Ondas al escuchar
        if phase == .listening {
            for k in 0..<3 {
                let age = t.truncatingRemainder(dividingBy: 0.7) + Double(k) * 0.7
                if age < 1.8 { arc(R * (0.3 + age * 0.38), 0, 2 * .pi, 1.5, 0.5 * (1 - age / 1.8)) }
            }
        }

        // Partículas en órbita
        for p in particles {
            let alpha = 0.25 + 0.55 * (0.5 + 0.5 * sin(t * 2 + p.twinkle))
            let x = cx + cos(p.angle) * R * p.radius
            let y = cy + sin(p.angle) * R * p.radius
            context.fill(Path(ellipseIn: CGRect(x: x - p.size, y: y - p.size, width: p.size * 2, height: p.size * 2)),
                         with: .color(color(hot, alpha)))
        }

        // Núcleo
        let pulse = 1 + 0.06 * sin(t * 2.2) + smoothLevel * 0.22
        let coreRadius = R * 0.24 * pulse
        let glow = Path(ellipseIn: CGRect(x: cx - coreRadius * 1.9, y: cy - coreRadius * 1.9,
                                          width: coreRadius * 3.8, height: coreRadius * 3.8))
        context.fill(glow, with: .radialGradient(
            Gradient(stops: [.init(color: .white.opacity(0.95), location: 0),
                             .init(color: color(hot, 0.9), location: 0.22),
                             .init(color: color(main, 0.45), location: 0.5),
                             .init(color: color(main, 0), location: 1)]),
            center: center, startRadius: 0, endRadius: CGFloat(coreRadius * 1.9)))
        arc(coreRadius * 1.08, 0, 2 * .pi, 1.2, 0.9, hot)
        arc(coreRadius * 1.35, -spin * 0.6, 2 * .pi, 2.5, 0.5, dash: [CGFloat(R * 0.02), CGFloat(R * 0.03)])

        // Rótulo sobre el anillo
        guard showLabel, R > 100 else { return }
        context.blendMode = .normal
        let label = Array(Self.label(phase))
        let radius = R * 0.995
        let spacing = (R * 0.052) / radius
        let startAngle = -Double.pi / 2 - Double(label.count - 1) * spacing / 2
        for (i, character) in label.enumerated() {
            let a = startAngle + Double(i) * spacing
            var letter = context
            let p = point(a, radius)
            letter.translateBy(x: p.x, y: p.y)
            letter.rotate(by: .radians(a + .pi / 2))
            letter.draw(Text(String(character)).font(Theme.mono(CGFloat(max(9, R * 0.05)))).foregroundColor(color(hot, 0.85)),
                        at: .zero)
        }
    }
}

// MARK: - Fondo

/// Fondo de JARVIS: la imagen holográfica, una rejilla en perspectiva y la viñeta.
struct HoloBackground: View {
    var body: some View {
        ZStack {
            Theme.background
            Image("HoloFondo")
                .resizable()
                .scaledToFill()
                .opacity(0.32)
            Canvas { context, size in
                // Suelo en rejilla que se pierde hacia el horizonte
                let horizon = size.height * 0.62
                var grid = Path()
                for i in -8...8 {
                    let step = CGFloat(i)
                    grid.move(to: CGPoint(x: size.width / 2 + step * size.width * 0.02, y: horizon))
                    grid.addLine(to: CGPoint(x: size.width / 2 + step * size.width * 0.16, y: size.height))
                }
                for j in 0..<9 {
                    let f = CGFloat(j * j) / 64
                    let y = horizon + (size.height - horizon) * f
                    grid.move(to: CGPoint(x: 0, y: y))
                    grid.addLine(to: CGPoint(x: size.width, y: y))
                }
                context.stroke(grid, with: .color(Theme.accent.opacity(0.10)), lineWidth: 1)
            }
            RadialGradient(colors: [.clear, Theme.background.opacity(0.85)], center: .center,
                           startRadius: 120, endRadius: 520)
        }
        .ignoresSafeArea()
        .accessibilityHidden(true)
    }
}

// MARK: - Tarjetas

/// Rectángulo con dos esquinas cortadas en diagonal, como las tarjetas del panel.
struct CutCornerShape: Shape {
    var cut: CGFloat = 14

    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.minX + cut, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - cut))
        path.addLine(to: CGPoint(x: rect.maxX - cut, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.minY + cut))
        path.closeSubpath()
        return path
    }
}

/// Las escuadras luminosas de las esquinas libres.
private struct CornerBrackets: Shape {
    func path(in rect: CGRect) -> Path {
        let l: CGFloat = 16
        var path = Path()
        path.move(to: CGPoint(x: rect.maxX - l - 6, y: rect.minY + 6))
        path.addLine(to: CGPoint(x: rect.maxX - 6, y: rect.minY + 6))
        path.addLine(to: CGPoint(x: rect.maxX - 6, y: rect.minY + 6 + l))
        path.move(to: CGPoint(x: rect.minX + 6, y: rect.maxY - 6 - l))
        path.addLine(to: CGPoint(x: rect.minX + 6, y: rect.maxY - 6))
        path.addLine(to: CGPoint(x: rect.minX + 6 + l, y: rect.maxY - 6))
        return path
    }
}

private struct HoloCard: ViewModifier {
    let accent: Color

    func body(content: Content) -> some View {
        content
            .background(
                CutCornerShape()
                    .fill(LinearGradient(colors: [Theme.surface.opacity(0.85), Theme.background.opacity(0.75)],
                                         startPoint: .top, endPoint: .bottom))
            )
            .overlay(CutCornerShape().stroke(accent.opacity(0.35), lineWidth: 1))
            .overlay(CornerBrackets().stroke(accent, lineWidth: 2).shadow(color: accent, radius: 4))
    }
}

extension View {
    func holoCard(accent: Color = Theme.accent) -> some View {
        modifier(HoloCard(accent: accent))
    }
}

/// Rótulo de tarjeta: «■ ENTRADA ——»
struct HoloLabel: View {
    let text: String
    var accent: Color = Theme.accent

    var body: some View {
        HStack(spacing: 8) {
            Rectangle().fill(accent).frame(width: 6, height: 6).shadow(color: accent, radius: 3)
            Text(text.uppercased())
                .font(Theme.mono(11))
                .tracking(2.5)
                .foregroundStyle(accent)
            Rectangle().fill(LinearGradient(colors: [accent.opacity(0.5), .clear], startPoint: .leading, endPoint: .trailing))
                .frame(height: 1)
        }
        .accessibilityHidden(true)
    }
}

// MARK: - Arranque

/// Al abrir la app: el núcleo se monta, comprueba los sistemas con datos reales
/// del Mac y saluda. Un toque lo salta.
struct BootView: View {
    var stays = false
    let onDone: () -> Void

    @State private var lines: [(name: String, value: String, warn: Bool)] = []
    @State private var shown = 0
    @State private var owner = ""
    @State private var assembled = false
    @State private var leaving = false

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            Image("HoloNucleo")
                .resizable()
                .scaledToFill()
                .blendMode(.screen)
                .opacity(assembled ? 0.35 : 0)
                .ignoresSafeArea()
            VStack(spacing: 18) {
                HoloCoreView(phase: shown >= lines.count && !lines.isEmpty ? .speaking : .thinking, showLabel: false,
                             level: { 0.35 })
                    .frame(width: 210, height: 210)
                    .scaleEffect(assembled ? 1 : 0.3)
                    .rotationEffect(.degrees(assembled ? 0 : -90))
                    .opacity(assembled ? 1 : 0)
                Text("J.A.R.V.I.S")
                    .font(Theme.display(30, weight: .heavy))
                    .tracking(9)
                    .foregroundStyle(Theme.ice)
                    .shadow(color: Theme.accent, radius: 12)
                Text("INICIANDO SISTEMAS")
                    .font(Theme.mono(12))
                    .tracking(5)
                    .foregroundStyle(Theme.accent)
                VStack(spacing: 7) {
                    ForEach(Array(lines.prefix(shown).enumerated()), id: \.offset) { _, line in
                        HStack(spacing: 8) {
                            Text(line.name).foregroundStyle(Theme.muted)
                            Rectangle().fill(Theme.accent.opacity(0.25)).frame(height: 1)
                            Text(line.value).foregroundStyle(line.warn ? Theme.warning : Theme.ok)
                        }
                        .font(Theme.mono(12))
                        .tracking(1.2)
                        .transition(.opacity.combined(with: .move(edge: .leading)))
                    }
                }
                .padding(.horizontal, 28)
                .frame(minHeight: 200, alignment: .top)
                if shown >= lines.count && !lines.isEmpty {
                    Text(greeting)
                        .font(Theme.display(22, weight: .semibold))
                        .foregroundStyle(Theme.ice)
                        .shadow(color: Theme.accent, radius: 10)
                        .transition(.opacity.combined(with: .scale(scale: 1.1)))
                }
            }
            VStack {
                Spacer()
                Text("Toca para entrar").font(Theme.mono(11)).tracking(3).foregroundStyle(Theme.muted)
                    .padding(.bottom, 12)
            }
        }
        .opacity(leaving ? 0 : 1)
        .scaleEffect(leaving ? 1.08 : 1)
        .contentShape(Rectangle())
        .onTapGesture { leave() }
        .task { await run() }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("JARVIS arrancando. Toca para entrar.")
        .accessibilityAddTraits(.isButton)
    }

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        let base = hour >= 6 && hour < 13 ? "Buenos días" : hour >= 13 && hour < 21 ? "Buenas tardes" : "Buenas noches"
        return owner.isEmpty ? "\(base)." : "\(base), \(owner)."
    }

    private func run() async {
        withAnimation(.spring(response: 1.0, dampingFraction: 0.75)) { assembled = true }
        let data = try? await JarvisAPI.dashboard()
        lines = Self.systemLines(data)
        owner = data?["owner"] as? String ?? ""
        try? await Task.sleep(for: .milliseconds(450))
        for _ in lines {
            guard !leaving else { return }
            withAnimation(.easeOut(duration: 0.2)) { shown += 1 }
            try? await Task.sleep(for: .milliseconds(240))
        }
        try? await Task.sleep(for: .milliseconds(1400))
        if !stays { leave() }
    }

    private func leave() {
        guard !leaving else { return }
        withAnimation(.easeIn(duration: 0.55)) { leaving = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.55) { onDone() }
    }

    private static func number(_ value: Any?) -> Double? { (value as? NSNumber)?.doubleValue }

    static func systemLines(_ data: [String: Any]?) -> [(name: String, value: String, warn: Bool)] {
        let speech = SFSpeechRecognizer.authorizationStatus() == .authorized
        var lines: [(name: String, value: String, warn: Bool)] = [
            ("ENLACE CON EL MAC", data == nil ? "SIN RESPUESTA" : "OK", data == nil),
            ("VOZ", speech ? "OK" : "SIN PERMISO", !speech),
        ]
        guard let data else { return lines }
        if let calendar = data["calendar"] as? [Any] {
            lines.append(("AGENDA", "\(calendar.count) \(calendar.count == 1 ? "CITA" : "CITAS") HOY", false))
        }
        if let email = data["email"] as? [String: Any], let unread = number(email["unread_total"]) {
            lines.append(("CORREO", "\(Int(unread)) SIN LEER", false))
        }
        if let car = data["car"] as? [String: Any] {
            var parts: [String] = []
            if let fuel = number(car["fuel_percent"]) { parts.append("\(Int(fuel.rounded())) %") }
            let locked = car["locked"] as? Bool
            if let locked { parts.append(locked ? "CERRADO" : "ABIERTO") }
            let tires = (car["tire_problems"] as? [Any])?.count ?? 0
            lines.append(("MERCEDES-AMG C 63", parts.isEmpty ? "EN LÍNEA" : parts.joined(separator: " · "), locked == false || tires > 0))
        }
        if let health = data["health"] as? [String: Any], let recovery = health["recovery"] as? [String: Any],
           let percent = number(recovery["recovery_percent"]) {
            lines.append(("WHOOP", "RECUPERACIÓN \(Int(percent.rounded())) %", false))
        }
        if let store = data["store"] as? [String: Any], let today = store["today"] as? [String: Any],
           let orders = number(today["orders"]) {
            lines.append(("TIENDA", "\(Int(orders)) PEDIDOS HOY", false))
        }
        if let weather = data["weather"] as? [String: Any], let temperature = number(weather["temperature_c"]) {
            lines.append(("EXTERIOR", "\(Int(temperature.rounded()))°", false))
        }
        return lines
    }
}

import AppIntents
import SwiftUI

#if DEBUG
/// Solo para las capturas automáticas del simulador (ver ios.yml):
/// JARVIS_CAPTURA=arranque|principal enseña esa pantalla sin estar conectado.
let captureMode = ProcessInfo.processInfo.environment["JARVIS_CAPTURA"].flatMap { $0.isEmpty ? nil : $0 }
#else
let captureMode: String? = nil
#endif

struct RootView: View {
    @EnvironmentObject private var session: Session
    // El arranque sale una vez cada vez que se abre la app.
    @State private var booting = captureMode != "principal"

    var body: some View {
        ZStack {
            HoloBackground()
            if session.pairing == nil && captureMode == nil {
                OnboardingView()
            } else {
                MainView()
                if booting {
                    BootView(stays: captureMode == "arranque") { booting = false }
                        .transition(.opacity)
                        .zIndex(1)
                }
            }
        }
    }
}

// MARK: - Conversación

struct MainView: View {
    @EnvironmentObject private var session: Session
    @StateObject private var conversation = ConversationModel()
    @State private var showSettings = false

    var body: some View {
        VStack(spacing: 0) {
            header
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(spacing: 14) {
                        HoloCoreView(phase: conversation.phase)
                            .frame(width: 290, height: 290)
                            .padding(.top, 4)
                        StatusLine(phase: conversation.phase, listener: conversation.listener)
                        if conversation.messages.isEmpty {
                            Suggestions()
                        }
                        ForEach(conversation.messages) { message in
                            MessageBubble(message: message).id(message.id)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
                }
                .scrollIndicators(.hidden)
                .onChange(of: conversation.messages) { _, messages in
                    guard let last = messages.last else { return }
                    withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
            MicButton(phase: conversation.phase) { conversation.micTapped() }
                .padding(.vertical, 12)
        }
        .sheet(isPresented: $showSettings) {
            SettingsView().environmentObject(session)
        }
        .task {
            guard captureMode == nil else { return }
            LocationProvider.shared.requestPermission()
            await PushRegistrar.shared.requestAuthorizationAndRegister()
        }
    }

    private var header: some View {
        VStack(spacing: 8) {
            HStack(spacing: 16) {
                Circle().fill(Theme.ok).frame(width: 7, height: 7).shadow(color: Theme.ok, radius: 4)
                Text("J.A.R.V.I.S")
                    .font(Theme.display(19, weight: .heavy))
                    .tracking(5)
                    .foregroundStyle(Theme.ice)
                    .shadow(color: Theme.accent.opacity(0.8), radius: 8)
                Spacer()
                TimelineView(.periodic(from: .now, by: 1)) { timeline in
                    Text(timeline.date, format: .dateTime.hour().minute())
                        .font(Theme.display(15, weight: .medium))
                        .foregroundStyle(Theme.ice)
                        .monospacedDigit()
                }
                if let panel = session.pairing?.panelURL {
                    Link(destination: panel) { Image(systemName: "square.grid.2x2") }
                        .accessibilityLabel("Abrir el panel")
                }
                Button { showSettings = true } label: { Image(systemName: "gearshape") }
                    .accessibilityLabel("Ajustes")
            }
            .font(.title3)
            Rectangle()
                .fill(LinearGradient(colors: [Theme.accent.opacity(0.05), Theme.accent.opacity(0.6), Theme.accent.opacity(0.05)],
                                     startPoint: .leading, endPoint: .trailing))
                .frame(height: 1)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }
}

struct StatusLine: View {
    let phase: ConversationModel.Phase
    @ObservedObject var listener: SpeechListener

    var body: some View {
        Group {
            switch phase {
            case .idle:
                Text("Toca el botón y habla")
            case .listening:
                Text(listener.transcript.isEmpty ? "Te escucho…" : listener.transcript)
                    .foregroundStyle(Theme.warning)
            case .thinking:
                Text("Pensando…")
            case .speaking:
                Text("Toca el botón para interrumpir")
            }
        }
        .font(Theme.mono(15))
        .tracking(1)
        .foregroundStyle(Theme.muted)
        .multilineTextAlignment(.center)
        .frame(minHeight: 40)
    }
}

struct Suggestions: View {
    private let examples = ["¿Qué tengo hoy?", "¿Tengo correos importantes?", "¿Cuánta gasolina tengo?", "¿Cómo he dormido?"]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HoloLabel(text: "Prueba a decir")
            ForEach(examples, id: \.self) { example in
                Text("«\(example)»").foregroundStyle(Theme.text)
            }
            Text("También con Siri: «Oye Siri, habla con JARVIS».")
                .font(.footnote)
                .foregroundStyle(Theme.muted)
                .padding(.top, 2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .holoCard()
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HoloLabel(text: label, accent: accent)
            Text(message.text)
                .font(message.role == .user ? Theme.mono(16) : .body)
                .foregroundStyle(message.role == .user ? Theme.warning : message.role == .error ? Theme.alert : Theme.ice)
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
        }
        .padding(16)
        .holoCard(accent: accent)
        .padding(message.role == .user ? .leading : .trailing, 28)
    }

    private var label: String {
        switch message.role {
        case .user: return "Tú"
        case .jarvis: return "JARVIS"
        case .error: return "Aviso"
        }
    }

    private var accent: Color {
        switch message.role {
        case .user: return Theme.warning
        case .jarvis: return Theme.accent
        case .error: return Theme.alert
        }
    }
}

/// El botón de hablar: un núcleo con anillos que giran; ámbar mientras escucha.
struct MicButton: View {
    let phase: ConversationModel.Phase
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            TimelineView(.animation) { timeline in
                let t = timeline.date.timeIntervalSinceReferenceDate
                ZStack {
                    Circle()
                        .stroke(color.opacity(0.55), style: StrokeStyle(lineWidth: 1.5, dash: [3, 6]))
                        .frame(width: 104, height: 104)
                        .rotationEffect(.degrees(t * 30))
                    Circle()
                        .trim(from: 0, to: 0.7)
                        .stroke(color.opacity(0.8), style: StrokeStyle(lineWidth: 2, lineCap: .round))
                        .frame(width: 92, height: 92)
                        .rotationEffect(.degrees(-t * (phase == .thinking ? 220 : 60)))
                    Image(systemName: icon)
                        .font(.system(size: 28, weight: .semibold))
                        .foregroundStyle(Theme.background)
                        .frame(width: 72, height: 72)
                        .background(Circle().fill(RadialGradient(colors: [.white, color], center: .center,
                                                                 startRadius: 2, endRadius: 46)))
                        .shadow(color: color.opacity(0.9), radius: 18)
                }
            }
            .frame(width: 110, height: 110)
        }
        .buttonStyle(.plain)
        .disabled(phase == .thinking)
        .accessibilityLabel(phase == .listening ? "Terminar de hablar" : "Hablar con JARVIS")
    }

    private var color: Color { phase == .listening ? Theme.warning : Theme.accent }

    private var icon: String {
        switch phase {
        case .idle: return "mic.fill"
        case .listening: return "stop.fill"
        case .thinking: return "ellipsis"
        case .speaking: return "speaker.wave.2.fill"
        }
    }
}

// MARK: - Ajustes

struct SettingsView: View {
    @EnvironmentObject private var session: Session
    @Environment(\.dismiss) private var dismiss
    @State private var confirmUnpair = false
    @State private var notifications = "…"

    var body: some View {
        NavigationStack {
            List {
                Section("Tu JARVIS") {
                    LabeledContent("Dirección", value: session.pairing?.baseURL.host ?? "—")
                    if let panel = session.pairing?.panelURL {
                        Link("Abrir el panel", destination: panel)
                    }
                }
                Section("Avisos") {
                    LabeledContent("Estado", value: notifications)
                    Button("Activar los avisos") {
                        Task {
                            await PushRegistrar.shared.requestAuthorizationAndRegister()
                            notifications = await PushRegistrar.shared.statusText()
                        }
                    }
                }
                Section {
                    Text("Di «Oye Siri, habla con JARVIS». Funciona también en el coche y con los AirPods.")
                    ShortcutsLink()
                } header: {
                    Text("Siri")
                } footer: {
                    Text("Para el coche: en la app Atajos → Automatización → CarPlay, «Se conecta» con «Saludo de JARVIS» y «Se desconecta» con «Me bajo del coche».")
                }
                Section {
                    Button("Desconectar este iPhone", role: .destructive) { confirmUnpair = true }
                } footer: {
                    Text("JARVIS \(appVersion)")
                }
            }
            .navigationTitle("Ajustes")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Listo") { dismiss() } }
            }
            .confirmationDialog("¿Desconectar este iPhone de JARVIS?", isPresented: $confirmUnpair, titleVisibility: .visible) {
                Button("Desconectar", role: .destructive) {
                    session.unpair()
                    dismiss()
                }
            }
            .task { notifications = await PushRegistrar.shared.statusText() }
        }
    }

    private var appVersion: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "?"
        let build = info?["CFBundleVersion"] as? String ?? "?"
        return "\(version) (\(build))"
    }
}

import AppIntents
import SwiftUI

struct RootView: View {
    @EnvironmentObject private var session: Session

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            if session.pairing == nil {
                OnboardingView()
            } else {
                MainView()
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
                    VStack(spacing: 16) {
                        ArcReactor(phase: conversation.phase)
                            .frame(width: 170, height: 170)
                            .padding(.top, 16)
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
                .onChange(of: conversation.messages) { _, messages in
                    guard let last = messages.last else { return }
                    withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
            MicButton(phase: conversation.phase) { conversation.micTapped() }
                .padding(.vertical, 14)
        }
        .sheet(isPresented: $showSettings) {
            SettingsView().environmentObject(session)
        }
        .task {
            LocationProvider.shared.requestPermission()
            await PushRegistrar.shared.requestAuthorizationAndRegister()
        }
    }

    private var header: some View {
        HStack(spacing: 18) {
            Text("J.A.R.V.I.S")
                .font(.system(.headline, design: .rounded))
                .tracking(4)
                .foregroundStyle(Theme.accent)
            Spacer()
            if let panel = session.pairing?.panelURL {
                Link(destination: panel) { Image(systemName: "square.grid.2x2") }
                    .accessibilityLabel("Abrir el panel")
            }
            Button { showSettings = true } label: { Image(systemName: "gearshape") }
                .accessibilityLabel("Ajustes")
        }
        .font(.title3)
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
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
                    .foregroundStyle(Theme.text)
            case .thinking:
                Text("Pensando…")
            case .speaking:
                Text("Toca el botón para interrumpir")
            }
        }
        .font(.callout)
        .foregroundStyle(Theme.muted)
        .multilineTextAlignment(.center)
        .frame(minHeight: 44)
    }
}

struct Suggestions: View {
    private let examples = ["¿Qué tengo hoy?", "¿Tengo correos importantes?", "¿Cuánta gasolina tengo?", "¿Cómo he dormido?"]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("PRUEBA A DECIR")
                .font(.caption.weight(.bold))
                .tracking(2)
                .foregroundStyle(Theme.accent)
            ForEach(examples, id: \.self) { example in
                Text("«\(example)»").foregroundStyle(Theme.text)
            }
            Text("También con Siri: «Oye Siri, habla con JARVIS».")
                .font(.footnote)
                .foregroundStyle(Theme.muted)
                .padding(.top, 4)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 14))
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 48) }
            Text(message.text)
                .foregroundStyle(message.role == .error ? Theme.warning : Theme.text)
                .padding(12)
                .background(message.role == .user ? Theme.accent.opacity(0.18) : Theme.surface,
                            in: RoundedRectangle(cornerRadius: 14))
            if message.role != .user { Spacer(minLength: 48) }
        }
    }
}

struct MicButton: View {
    let phase: ConversationModel.Phase
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 30, weight: .semibold))
                .foregroundStyle(Theme.background)
                .frame(width: 78, height: 78)
                .background(Circle().fill(color))
                .shadow(color: color.opacity(0.7), radius: 18)
        }
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

/// El «reactor» de JARVIS: late más fuerte cuando escucha o habla.
struct ArcReactor: View {
    let phase: ConversationModel.Phase
    @State private var pulse = false

    var body: some View {
        ZStack {
            Circle().stroke(Theme.accent.opacity(0.35), lineWidth: 12).blur(radius: 8)
            Circle().stroke(Theme.accent, lineWidth: 4)
            Circle()
                .inset(by: 22)
                .stroke(Theme.accent.opacity(0.75), style: StrokeStyle(lineWidth: 13, dash: [24, 8]))
                .rotationEffect(.degrees(pulse ? 30 : 0))
            Circle()
                .inset(by: 52)
                .fill(RadialGradient(colors: [.white, Theme.accent.opacity(0.9), Theme.accent.opacity(0.25)],
                                     center: .center, startRadius: 2, endRadius: 40))
                .scaleEffect(pulse ? scale : 1)
                .shadow(color: Theme.accent, radius: pulse ? 26 : 10)
        }
        .animation(.easeInOut(duration: phase == .thinking ? 0.6 : 1.6).repeatForever(autoreverses: true), value: pulse)
        .onAppear { pulse = true }
        .onChange(of: phase) { _, _ in
            pulse = false
            DispatchQueue.main.async { pulse = true }
        }
        .accessibilityHidden(true)
    }

    private var scale: CGFloat {
        switch phase {
        case .listening: return 1.18
        case .speaking: return 1.12
        default: return 1.04
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

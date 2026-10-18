import Foundation

struct ChatMessage: Identifiable, Equatable {
    enum Role { case user, jarvis, error }

    let id = UUID()
    let role: Role
    let text: String
}

/// Una conversación con JARVIS: escuchar → preguntar al Mac → hablar → hacer lo
/// que pida (navegar, llamar…) → volver a escuchar si ha hecho una pregunta.
@MainActor
final class ConversationModel: ObservableObject {
    enum Phase { case idle, listening, thinking, speaking }

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var messages: [ChatMessage] = []

    let listener = SpeechListener()
    private var hasPermissions = false

    func micTapped() {
        switch phase {
        case .idle:
            Task { await listen() }
        case .listening:
            listener.finish()
        case .speaking:
            VoicePlayer.shared.stop()
        case .thinking:
            break
        }
    }

    func listen() async {
        if !hasPermissions {
            hasPermissions = await SpeechListener.requestPermissions()
            guard hasPermissions else {
                messages.append(ChatMessage(role: .error, text: "Para hablar con JARVIS, permite el micrófono y el reconocimiento de voz en Ajustes → JARVIS."))
                return
            }
        }
        do {
            phase = .listening
            try listener.start { [weak self] text in
                Task { @MainActor in await self?.send(text) }
            }
        } catch {
            phase = .idle
            messages.append(ChatMessage(role: .error, text: error.localizedDescription))
        }
    }

    func send(_ text: String) async {
        guard !text.isEmpty else {
            phase = .idle
            return
        }
        messages.append(ChatMessage(role: .user, text: text))
        phase = .thinking
        do {
            let response = try await JarvisAPI.ask(text, location: LocationProvider.shared.lastLocation)
            messages.append(ChatMessage(role: .jarvis, text: response.text))
            phase = .speaking
            await VoicePlayer.shared.speak(text: response.text, audioBase64: response.audio)
            let urls = await ClientActions.urls(for: response.clientActions)
            await ClientActions.open(urls)
            phase = .idle
            // Si JARVIS ha preguntado algo («¿Lo envío?»), vuelve a escuchar solo.
            if response.expectsReply && urls.isEmpty {
                await listen()
            }
        } catch {
            phase = .idle
            messages.append(ChatMessage(role: .error, text: error.localizedDescription))
        }
    }
}

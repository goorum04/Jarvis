import AVFoundation
import Speech

/// Escucha a Nacho y lo pasa a texto. Termina sola cuando deja de hablar.
@MainActor
final class SpeechListener: ObservableObject {
    @Published private(set) var transcript = ""
    @Published private(set) var isListening = false

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "es-ES"))
    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var silenceTimer: Timer?
    private var onFinish: ((String) -> Void)?

    static func requestPermissions() async -> Bool {
        let speech = await withCheckedContinuation { (continuation: CheckedContinuation<Bool, Never>) in
            SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0 == .authorized) }
        }
        let microphone = await AVAudioApplication.requestRecordPermission()
        return speech && microphone
    }

    func start(onFinish: @escaping (String) -> Void) throws {
        stop()
        guard let recognizer, recognizer.isAvailable else {
            throw JarvisError.server("El reconocimiento de voz no está disponible ahora mismo.")
        }
        self.onFinish = onFinish
        transcript = ""

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth, .duckOthers])
        try session.setActive(true, options: .notifyOthersOnDeactivation)

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.addsPunctuation = true
        self.request = request

        Self.installTap(on: engine.inputNode, feeding: request)
        engine.prepare()
        try engine.start()
        isListening = true

        task = Self.recognize(with: recognizer, request: request) { [weak self] text, isFinal, failed in
            guard let self, self.isListening else { return }
            if let text { self.transcript = text }
            if isFinal || failed {
                self.finish()
            } else {
                self.restartSilenceTimer()
            }
        }
        restartSilenceTimer(after: 6)  // si no dice nada, se deja de escuchar
    }

    /// Termina de escuchar y entrega lo que ha dicho.
    func finish() {
        guard isListening else { return }
        let text = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        let callback = onFinish
        stop()
        callback?(text)
    }

    func stop() {
        silenceTimer?.invalidate()
        silenceTimer = nil
        if engine.isRunning { engine.stop() }
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        request = nil
        task?.cancel()
        task = nil
        isListening = false
        onFinish = nil
    }

    private func restartSilenceTimer(after seconds: TimeInterval = 1.4) {
        silenceTimer?.invalidate()
        silenceTimer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { [weak self] _ in
            Task { @MainActor in self?.finish() }
        }
    }

    // El audio y el reconocimiento llegan en otros hilos: estas dos funciones
    // no dependen del hilo principal y le pasan los resultados.
    nonisolated private static func installTap(on input: AVAudioInputNode, feeding request: SFSpeechAudioBufferRecognitionRequest) {
        input.removeTap(onBus: 0)
        let format = input.outputFormat(forBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            request.append(buffer)
        }
    }

    nonisolated private static func recognize(
        with recognizer: SFSpeechRecognizer, request: SFSpeechAudioBufferRecognitionRequest,
        update: @escaping @MainActor (String?, Bool, Bool) -> Void
    ) -> SFSpeechRecognitionTask {
        recognizer.recognitionTask(with: request) { result, error in
            let text = result?.bestTranscription.formattedString
            let isFinal = result?.isFinal ?? false
            let failed = result == nil && error != nil
            Task { @MainActor in update(text, isFinal, failed) }
        }
    }
}

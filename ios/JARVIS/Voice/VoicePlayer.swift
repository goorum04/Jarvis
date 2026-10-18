import AVFoundation

/// Reproduce la voz de JARVIS (el MP3 de ElevenLabs que manda el Mac) o, si no
/// llega, la voz del sistema en castellano. Baja la música mientras habla.
final class VoicePlayer: NSObject, AVAudioPlayerDelegate, AVSpeechSynthesizerDelegate {
    static let shared = VoicePlayer()

    private var player: AVAudioPlayer?
    private let synthesizer = AVSpeechSynthesizer()
    private var continuation: CheckedContinuation<Void, Never>?

    override init() {
        super.init()
        synthesizer.delegate = self
    }

    /// Vuelve cuando ha terminado de hablar (o si se le interrumpe).
    func speak(text: String, audioBase64: String?) async {
        stop()
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
        try? session.setActive(true)
        await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
            DispatchQueue.main.async {
                self.continuation = continuation
                if let audioBase64, let data = Data(base64Encoded: audioBase64),
                   let player = try? AVAudioPlayer(data: data) {
                    self.player = player
                    player.delegate = self
                    player.isMeteringEnabled = true
                    if player.play() { return }
                }
                let utterance = AVSpeechUtterance(string: text)
                utterance.voice = AVSpeechSynthesisVoice(language: "es-ES")
                self.synthesizer.speak(utterance)
            }
        }
        try? session.setActive(false, options: .notifyOthersOnDeactivation)
    }

    /// Volumen de la voz en este instante (0…1), para que el núcleo la siga.
    /// Se llama desde la pantalla, en el hilo principal.
    func level() -> Double {
        if let player, player.isPlaying {
            player.updateMeters()
            let decibels = Double(player.averagePower(forChannel: 0))
            return max(0, min(1, (decibels + 45) / 45))
        }
        if synthesizer.isSpeaking {
            let t = Date().timeIntervalSinceReferenceDate
            return 0.35 + 0.25 * sin(t * 9) * sin(t * 2.3)
        }
        return 0
    }

    func stop() {
        DispatchQueue.main.async {
            self.player?.stop()
            self.player = nil
            if self.synthesizer.isSpeaking { self.synthesizer.stopSpeaking(at: .immediate) }
            self.finished()
        }
    }

    private func finished() {
        continuation?.resume()
        continuation = nil
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) { finished() }

    func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) { finished() }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) { finished() }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) { finished() }
}

import AppIntents
import UIKit

/// «Oye Siri, habla con JARVIS»: Siri pregunta qué necesita, se lo manda al Mac
/// y lee la respuesta. Si JARVIS pregunta algo («¿Lo envío?»), Siri vuelve a
/// escuchar sin que haya que repetir nada. Funciona igual en CarPlay.
struct AskJarvisIntent: AppIntent, ForegroundContinuableIntent {
    static var title: LocalizedStringResource = "Hablar con JARVIS"
    static var description = IntentDescription("Pídele algo a JARVIS: tu agenda, el correo, el coche, cómo has dormido…")
    static var openAppWhenRun = false

    @Parameter(title: "Petición", requestValueDialog: IntentDialog("¿Qué necesitas?"))
    var request: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        var text = request
        for _ in 0..<6 {
            let answer = try await JarvisAPI.ask(text, location: LocationProvider.shared.lastLocation)
            // Navegar, llamar o preparar un WhatsApp necesita abrir el iPhone.
            let urls = await ClientActions.urls(for: answer.clientActions)
            if !urls.isEmpty {
                throw needsToContinueInForegroundError(IntentDialog(stringLiteral: answer.text)) {
                    await ClientActions.open(urls)
                }
            }
            guard answer.expectsReply else {
                return .result(dialog: IntentDialog(stringLiteral: answer.text))
            }
            text = try await $request.requestValue(IntentDialog(stringLiteral: answer.text))
        }
        return .result(dialog: "Seguimos cuando quieras.")
    }
}

/// Para la automatización de CarPlay «Se conecta»: JARVIS saluda con su propia
/// voz (gasolina, tiempo, próxima cita, correos y pedidos), bajando la música.
struct GreetingIntent: AudioPlaybackIntent {
    static var title: LocalizedStringResource = "Saludo de JARVIS"
    static var description = IntentDescription("JARVIS te saluda con tu día. Pensado para la automatización de CarPlay «Se conecta».")
    static var openAppWhenRun = false

    func perform() async throws -> some IntentResult {
        let spoken: SpokenResponse
        do {
            spoken = try await JarvisAPI.greeting(location: LocationProvider.shared.lastLocation)
        } catch {
            spoken = SpokenResponse(text: error.localizedDescription, audio: nil)
        }
        // Se habla en segundo plano: el atajo termina ya y la voz sigue sonando.
        Task { await VoicePlayer.shared.speak(text: spoken.text, audioBase64: spoken.audio) }
        return .result()
    }
}

/// Para la automatización de CarPlay «Se desconecta»: JARVIS mira al minuto si
/// el coche ha quedado cerrado y avisa si no. No dice nada si todo está bien.
struct CarLeftIntent: AppIntent {
    static var title: LocalizedStringResource = "Me bajo del coche"
    static var description = IntentDescription("JARVIS comprueba al minuto si el coche ha quedado cerrado. Para la automatización de CarPlay «Se desconecta».")
    static var openAppWhenRun = false

    func perform() async throws -> some IntentResult {
        try? await JarvisAPI.carLeft()
        return .result()
    }
}

/// Frases de Siri que funcionan nada más instalar la app, sin crear atajos.
struct JarvisShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AskJarvisIntent(),
            phrases: [
                "Habla con \(.applicationName)",
                "Pregunta a \(.applicationName)",
                "Oye \(.applicationName)",
                "\(.applicationName)",
            ],
            shortTitle: "Hablar con JARVIS",
            systemImageName: "waveform"
        )
        AppShortcut(
            intent: GreetingIntent(),
            phrases: ["Saludo de \(.applicationName)", "Buenos días \(.applicationName)"],
            shortTitle: "Saludo",
            systemImageName: "car.fill"
        )
        AppShortcut(
            intent: CarLeftIntent(),
            phrases: ["Me bajo del coche con \(.applicationName)"],
            shortTitle: "Me bajo del coche",
            systemImageName: "lock.open"
        )
    }
}

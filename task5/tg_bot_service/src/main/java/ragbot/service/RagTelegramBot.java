package ragbot.service;

import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;

import org.springframework.beans.factory.annotation.Value;

import org.telegram.telegrambots.bots.TelegramLongPollingBot;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.methods.GetMe;
import org.telegram.telegrambots.meta.api.objects.User;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;



@Component
public class RagTelegramBot extends TelegramLongPollingBot {
    private static final Logger log = LoggerFactory.getLogger(RagTelegramBot.class);

    private final RagClient ragClient;
    private final String username;

    public RagTelegramBot(
            @Value("${telegram.bot.token}") String token,
            @Value("${telegram.bot.username}") String username,
            RagClient ragClient
    ) {
        super(token);

        this.username = username;
        this.ragClient = ragClient;

        log.info("[BOT] constructed. username=@{}", username);
    }

    @PostConstruct
    public void init() {
        log.info("[BOT] init()");
        try {
            User me = execute(new GetMe());
            log.info("[BOT] getMe OK: id={} username=@{}", me.getId(), me.getUserName());
        } catch (Exception e) {
            log.error("[BOT] getMe FAILED", e);
        }
    }

    @Override
    public String getBotUsername() {
        return username;
    }

    @Override
    public void onUpdateReceived(Update update) {
        if (!update.hasMessage() || !update.getMessage().hasText()) {
            return;
        }

        String text = update.getMessage().getText();
        Long chatId = update.getMessage().getChatId();

        if ("/start".equals(text)) {
            send(chatId,
                    "Добро пожаловать в мир сказочных сущностей и мест.\n" +
                            "Я отвечаю на вопросы строго по базе знаний.\n" +
                            "Если ответа нет — честно скажу «я не знаю»."
            );
            return;
        }

        String answer = ragClient.ask(text);
        send(chatId, answer);
    }

    private void send(Long chatId, String text) {
        try {
            execute(
                    SendMessage.builder()
                            .chatId(chatId.toString())
                            .text(text)
                            .build()
            );
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}

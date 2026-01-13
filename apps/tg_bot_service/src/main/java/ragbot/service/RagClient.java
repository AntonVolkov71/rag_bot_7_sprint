package ragbot.service;

import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import org.springframework.beans.factory.annotation.Value;
import ragbot.dto.AskRequest;
import ragbot.dto.AskResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Component
public class RagClient {
    private static final Logger log = LoggerFactory.getLogger(RagClient.class);

    private final RestTemplate restTemplate = new RestTemplate();
    private final String baseUrl;

    public RagClient(@Value("${rag.base-url}") String baseUrl) {
        this.baseUrl = baseUrl;
    }

    public String ask(String question) {
        log.info("[RagClient] question=@{} ", question);

        AskRequest req = new AskRequest(question);

        AskResponse resp = restTemplate.postForObject(
                baseUrl + "/ask",
                req,
                AskResponse.class
        );

        if (resp == null) {
            return "Ошибка: пустой ответ от сервиса.";
        }

        return resp.answer();
    }
}

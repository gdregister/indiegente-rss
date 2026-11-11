# Indiegente — feed RSS não oficial

A RTP não publica RSS para o [Indiegente](https://www.rtp.pt/play/p257/indiegente) (Antena 3).
Este repositório gera um, de 3 em 3 horas, com os links diretos para os MP3 do RTP Play.

Feed: `https://<utilizador>.github.io/<repositório>/feed.xml`

- `generate.py` — lê o RTP Play, junta episódios novos a `episodes.json` e escreve `docs/feed.xml`
- `.github/workflows/update.yml` — corre o script automaticamente
- GitHub Pages serve a pasta `docs/`

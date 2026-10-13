# ORBE Motion — Tema Azul Noturno e otimização de animação

## Identidade visual
- Fundo azul-marinho profundo e painéis azul-ardósia.
- Azul elétrico para foco, seleção e indicador de tempo atual.
- Violeta discreto para keyframes selecionados.
- Transições da interface reduzidas de 100 ms para 80 ms. Isso afeta a resposta visual da interface, não altera a velocidade nem o timing das animações do projeto.

## Recursos de desempenho já existentes
- O visualizador possui cache de frames em RAM e fila de renderização com prioridade para o frame atualmente visível.
- O código também prevê prefetch de frames e cache de camadas no motor de renderização.
- As configurações de memória/cache devem ser ajustadas em **Configurações > Memória e CPU** conforme a RAM disponível e a resolução da composição.

## Recomendações para projetos pesados
1. Use resolução de pré-visualização reduzida durante a edição e resolução máxima para exportação.
2. Diminua temporariamente a resolução da composição quando estiver ajustando animações com muitos efeitos.
3. Evite manter várias composições pesadas reproduzindo simultaneamente.
4. Deixe o cache aquecer antes de avaliar a reprodução em tempo real.
5. Teste projetos representativos e compare FPS/tempo por quadro antes de declarar ganho de desempenho.

## Limite de validação
Esta versão aplica a paleta no tema e reduz o tempo das transições de UI. Não se afirma ganho de FPS de renderização sem benchmark de build executável em Windows.

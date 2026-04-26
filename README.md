# RAG_IA
Criação de um agente chatbot, em um modelo de arquitetura conhecido por RAG AI.
Essa ia foi feita pensando em uso empresarial e ainda se encontra em desenvolvimento.


INFORMAÇÕES IMPORTANTES PARA FUNCIONAMENTO

- É preciso o uso de uma chave api da openai, para isso insira uma em ".env" para o funcionamento;

- É necessário o uso de PDF contendo as informações para serem utilizadas pela ia. Esses PDF devem
  ser inseridos na pasta com nome "base";

- Para a preparação do banco de dados vetorizado é necessário que seja executado 1 vez a função "criar db";

- Após a execução desses passos o uso da ia é estritamente apenas através da função main:

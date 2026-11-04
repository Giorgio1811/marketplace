from django.db.models import F
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly

from .models import Pedido, Produto
from .serializers import PedidoSerializer, ProdutoSerializer


class ProdutoListCreateView(generics.ListCreateAPIView):
    serializer_class = ProdutoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Produto.objects.select_related("categoria").order_by("nome")
        categoria = self.request.query_params.get("categoria")
        if categoria:
            queryset = queryset.filter(categoria_id=categoria)
        busca = self.request.query_params.get("busca")
        if busca:
            queryset = queryset.filter(nome__icontains=busca)
        preco_minimo = self.request.query_params.get("preco_minimo")
        if preco_minimo:
            queryset = queryset.filter(preco__gte=preco_minimo)
        preco_maximo = self.request.query_params.get("preco_maximo")
        if preco_maximo:
            queryset = queryset.filter(preco__lte=preco_maximo)
        if self.request.query_params.get("disponivel") == "true":
            queryset = queryset.filter(estoque__gt=0)
        return queryset

    def perform_create(self, serializer):
        serializer.save(vendedor=self.request.user)


class PedidoCreateView(generics.CreateAPIView):
    queryset = Pedido.objects.all()
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]

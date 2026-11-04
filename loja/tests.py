from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Avaliacao, Categoria, ItemPedido, Pedido, Produto

User = get_user_model()


class MarketplaceTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user("vendedor", password="x", is_staff=True)
        self.comprador = User.objects.create_user("cliente", password="x")
        self.categoria = Categoria.objects.create(nome="Livros")
        self.produto = Produto.objects.create(
            vendedor=self.vendedor, categoria=self.categoria,
            nome="Livro", preco=Decimal("10.00"), estoque=3,
        )
        self.client.force_login(self.comprador)

    def add(self, quantidade=1):
        self.client.post(reverse("adicionar_carrinho", args=[self.produto.pk]), follow=True)
        session = self.client.session
        session["carrinho"][str(self.produto.pk)] = quantidade
        session.save()

    def test_checkout_grava_historico_baixa_estoque_e_limpa_sessao(self):
        self.add(2)
        response = self.client.post(reverse("checkout"))
        self.assertRedirects(response, reverse("catalogo"))
        item = ItemPedido.objects.get()
        self.assertEqual(item.preco_unitario, Decimal("10.00"))
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 1)
        self.assertEqual(self.client.session["carrinho"], {})

    def test_checkout_sem_estoque_e_atomico(self):
        self.add(4)
        self.client.post(reverse("checkout"))
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertTrue(self.client.session["carrinho"])
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 3)

    def test_checkout_reverte_erro_no_meio(self):
        self.add(1)
        with patch("loja.views.ItemPedido.objects.create", side_effect=RuntimeError("falha")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("checkout"))
        self.assertEqual(Pedido.objects.count(), 0)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 3)

    def test_api_produtos_publica_leitura(self):
        response = APIClient().get(reverse("api-produtos"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["nome"], "Livro")

    def test_api_produtos_filtra_por_busca_preco_e_disponibilidade(self):
        Produto.objects.create(
            vendedor=self.vendedor, categoria=self.categoria,
            nome="Caderno", preco=Decimal("3.00"), estoque=0,
        )
        response = APIClient().get(
            reverse("api-produtos"),
            {"busca": "liv", "preco_minimo": "9", "preco_maximo": "11", "disponivel": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["nome"] for item in response.json()], ["Livro"])

    def test_api_rejeita_faixa_de_preco_invalida(self):
        response = APIClient().get(
            reverse("api-produtos"),
            {"preco_minimo": "20", "preco_maximo": "10"},
        )
        self.assertEqual(response.status_code, 400)

    def test_api_produtos_exige_login_para_escrita(self):
        response = APIClient().post(reverse("api-produtos"), {"nome": "Outro"})
        self.assertIn(response.status_code, (401, 403))

    def test_api_pedido_ignora_preco_enviado(self):
        api = APIClient()
        api.force_authenticate(self.comprador)
        response = api.post(
            reverse("api-pedidos"),
            {"itens": [{"produto": self.produto.pk, "quantidade": 1, "preco_unitario": "0.01"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(ItemPedido.objects.get().preco_unitario, Decimal("10.00"))

    def test_pedido_api_sem_estoque_e_atomico(self):
        api = APIClient()
        api.force_authenticate(self.comprador)
        response = api.post(
            reverse("api-pedidos"),
            {"itens": [{"produto": self.produto.pk, "quantidade": 4}]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Pedido.objects.count(), 0)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.estoque, 3)

    def test_pedido_api_exige_itens(self):
        api = APIClient()
        api.force_authenticate(self.comprador)
        response = api.post(reverse("api-pedidos"), {"itens": []}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_login_preserva_carrinho_anonimo(self):
        self.client.logout()
        self.add(2)
        response = self.client.post(
            reverse("rest_framework:login"),
            {"username": "cliente", "password": "x", "next": reverse("carrinho")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["carrinho"][str(self.produto.pk)], 2)

    def test_carrinho_anonimo_exibe_login(self):
        self.client.logout()
        self.add()
        response = self.client.get(reverse("carrinho"))
        self.assertContains(response, "entre na sua conta")
        self.assertNotContains(response, "Finalizar compra")

    def test_catalogo_consome_api_e_localstorage(self):
        response = self.client.get(reverse("catalogo"))
        self.assertContains(response, "/api/produtos/")
        self.assertContains(response, "localStorage")

    def test_adicao_por_fetch_retorna_contador_json(self):
        response = self.client.post(
            reverse("adicionar_carrinho", args=[self.produto.pk]),
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["itens"], 1)

    def test_produto_nao_permite_preco_negativo(self):
        produto = Produto(
            vendedor=self.vendedor, categoria=self.categoria,
            nome="Inválido", preco=Decimal("-1.00"), estoque=1,
        )
        with self.assertRaises(ValidationError):
            produto.full_clean()

    def test_admin_vendedor_so_ve_produtos_proprios(self):
        outro = User.objects.create_user("outro", password="x", is_staff=True)
        Produto.objects.create(
            vendedor=outro, categoria=self.categoria,
            nome="Produto de outro", preco=Decimal("5.00"), estoque=1,
        )
        permissions = Permission.objects.filter(
            content_type__app_label="loja", content_type__model="produto"
        )
        self.vendedor.user_permissions.set(permissions)
        self.client.force_login(self.vendedor)
        response = self.client.get("/admin/loja/produto/")
        self.assertContains(response, "Livro")
        self.assertNotContains(response, "Produto de outro")

    def test_comprador_pode_avaliar_produto_que_comprou(self):
        self.add(1)
        self.client.post(reverse("checkout"))
        api = APIClient()
        api.force_authenticate(self.comprador)
        response = api.post(
            reverse("api-avaliacoes", args=[self.produto.pk]),
            {"nota": 5, "comentario": "Excelente"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Avaliacao.objects.get().nota, 5)

    def test_usuario_sem_compra_nao_pode_avaliar(self):
        api = APIClient()
        api.force_authenticate(self.comprador)
        response = api.post(
            reverse("api-avaliacoes", args=[self.produto.pk]),
            {"nota": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_avaliacao_duplicada_e_rejeitada(self):
        self.add(1)
        self.client.post(reverse("checkout"))
        Avaliacao.objects.create(produto=self.produto, usuario=self.comprador, nota=4)
        api = APIClient()
        api.force_authenticate(self.comprador)
        response = api.post(
            reverse("api-avaliacoes", args=[self.produto.pk]),
            {"nota": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

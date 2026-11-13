import http from '@/api/http'
import type {
  Category,
  FavoriteState,
  ProductDetail,
  ProductPage,
  ProductSort,
  ProductSummary,
} from '@/types/catalog'

export interface ProductQuery {
  category_id?: number
  q?: string
  page?: number
  page_size?: number
  sort?: ProductSort
}

export async function fetchCategories(): Promise<Category[]> {
  const { data } = await http.get<Category[]>('/categories')
  return data
}

export async function fetchProducts(
  query: ProductQuery = {},
): Promise<ProductPage> {
  const { data } = await http.get<ProductPage>('/products', { params: query })
  return data
}

export async function fetchProduct(id: number): Promise<ProductDetail> {
  const { data } = await http.get<ProductDetail>(`/products/${id}`)
  return data
}

export async function fetchFavorites(): Promise<ProductSummary[]> {
  const { data } = await http.get<ProductSummary[]>('/favorites')
  return data
}

export async function addFavorite(id: number): Promise<FavoriteState> {
  const { data } = await http.post<FavoriteState>(`/products/${id}/favorite`)
  return data
}

export async function removeFavorite(id: number): Promise<FavoriteState> {
  const { data } = await http.delete<FavoriteState>(`/products/${id}/favorite`)
  return data
}

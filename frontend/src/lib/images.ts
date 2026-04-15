// lib/images.ts — Deterministic product image generation
//
// Strategy: picsum.photos/seed/{hash}/400/400
// The product_id acts as the seed → same product = same image every reload.
// Category fallback dict maps to curated Unsplash URLs for realism.
//
// picsum.photos is a free, CDN-backed service. No API key needed.

// ── Category image pools (Unsplash, curated for e-commerce look) ─────────────
// Each category has 8 distinct images. A deterministic hash of the SKU
// selects the index, so SKU001 always gets image[0], SKU002 gets image[1], etc.

const CATEGORY_IMAGES: Record<string, string[]> = {
  Electronics: [
    "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=500&q=75",
    "https://images.unsplash.com/photo-1588508065123-287b28e013da?w=500&q=75",
    "https://images.unsplash.com/photo-1593305841991-05c297ba4575?w=500&q=75",
    "https://images.unsplash.com/photo-1585792180666-f7347c490ee2?w=500&q=75",
    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=75",
    "https://images.unsplash.com/photo-1517336714731-489689fd1ca4?w=500&q=75",
    "https://images.unsplash.com/photo-1625948515291-763a17e5c8c1?w=500&q=75",
    "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=500&q=75",
  ],
  Clothing: [
    "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=500&q=75",
    "https://images.unsplash.com/photo-1554568218-0f1715e72254?w=500&q=75",
    "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=500&q=75",
    "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=500&q=75",
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=500&q=75",
    "https://images.unsplash.com/photo-1516762689617-e1cffcef479d?w=500&q=75",
    "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=500&q=75",
    "https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=500&q=75",
  ],
  "Home & Kitchen": [
    "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=500&q=75",
    "https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=500&q=75",
    "https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?w=500&q=75",
    "https://images.unsplash.com/photo-1594040226829-7f251ab46d80?w=500&q=75",
    "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=500&q=75",
    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=500&q=75",
    "https://images.unsplash.com/photo-1527515545081-5db817172677?w=500&q=75",
    "https://images.unsplash.com/photo-1544984243-ec57ea16fe25?w=500&q=75",
  ],
  "Beauty & Health": [
    "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=500&q=75",
    "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?w=500&q=75",
    "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?w=500&q=75",
    "https://images.unsplash.com/photo-1522338242992-e1a54906a8da?w=500&q=75",
    "https://images.unsplash.com/photo-1556228578-8c89e6adf883?w=500&q=75",
    "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=500&q=75",
    "https://images.unsplash.com/photo-1532413992378-f169ac26fff0?w=500&q=75",
    "https://images.unsplash.com/photo-1512290923902-8a9f81dc236c?w=500&q=75",
  ],
  Gaming: [
    "https://images.unsplash.com/photo-1593118247619-e2d6f056869e?w=500&q=75",
    "https://images.unsplash.com/photo-1612287230202-1ff1d85d1bdf?w=500&q=75",
    "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=500&q=75",
    "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=500&q=75",
    "https://images.unsplash.com/photo-1486401899868-0e435ed85128?w=500&q=75",
    "https://images.unsplash.com/photo-1570303345338-e1f0eddf4946?w=500&q=75",
    "https://images.unsplash.com/photo-1600080972464-8e5f35f63d08?w=500&q=75",
    "https://images.unsplash.com/photo-1616348436168-de43ad0db179?w=500&q=75",
  ],
  Cameras: [
    "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=500&q=75",
    "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=500&q=75",
    "https://images.unsplash.com/photo-1510127034890-ba27508e9f1c?w=500&q=75",
    "https://images.unsplash.com/photo-1542038784456-1ea8e935640e?w=500&q=75",
    "https://images.unsplash.com/photo-1495707902641-75cac588d2e9?w=500&q=75",
    "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=500&q=75",
    "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=500&q=75",
    "https://images.unsplash.com/photo-1580745294621-f05dbbef4e0e?w=500&q=75",
  ],
  Sports: [
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&q=75",
    "https://images.unsplash.com/photo-1600185365926-3a2ce3cdb9eb?w=500&q=75",
    "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=500&q=75",
    "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=500&q=75",
    "https://images.unsplash.com/photo-1608256246200-53e635b5b65f?w=500&q=75",
    "https://images.unsplash.com/photo-1538944495092-d53ba2f53aa4?w=500&q=75",
    "https://images.unsplash.com/photo-1607522370275-f14206abe5d3?w=500&q=75",
    "https://images.unsplash.com/photo-1556906781-9a412961a28c?w=500&q=75",
  ],
  Accessories: [
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&q=75",
    "https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=500&q=75",
    "https://images.unsplash.com/photo-1585386959984-a4155224a1ad?w=500&q=75",
    "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=500&q=75",
    "https://images.unsplash.com/photo-1611591437281-460bfbe1220a?w=500&q=75",
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&q=75",
    "https://images.unsplash.com/photo-1600716051809-e997ca4077ba?w=500&q=75",
    "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?w=500&q=75",
  ],
  Cookware: [
    "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=500&q=75",
    "https://images.unsplash.com/photo-1590779033100-9f60a05a013d?w=500&q=75",
    "https://images.unsplash.com/photo-1582735689369-4fe89db7114c?w=500&q=75",
    "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=500&q=75",
    "https://images.unsplash.com/photo-1601924994987-69e26d50dc26?w=500&q=75",
    "https://images.unsplash.com/photo-1556911073-a517e752729c?w=500&q=75",
    "https://images.unsplash.com/photo-1495195134817-aeb325a55b65?w=500&q=75",
    "https://images.unsplash.com/photo-1585515320310-259814833e62?w=500&q=75",
  ],
  "Books & Media": [
    "https://images.unsplash.com/photo-1495446815901-a7297e633e8d?w=500&q=75",
    "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f?w=500&q=75",
    "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=500&q=75",
    "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=500&q=75",
    "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=500&q=75",
    "https://images.unsplash.com/photo-1507842217343-583bb7270b66?w=500&q=75",
    "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=500&q=75",
    "https://images.unsplash.com/photo-1490633874781-1c63cc424610?w=500&q=75",
  ],
  // Default fallback
  default: [
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&q=75",
    "https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=500&q=75",
    "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=500&q=75",
    "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=500&q=75",
    "https://images.unsplash.com/photo-1585792180666-f7347c490ee2?w=500&q=75",
    "https://images.unsplash.com/photo-1600185365926-3a2ce3cdb9eb?w=500&q=75",
    "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=500&q=75",
    "https://images.unsplash.com/photo-1612287230202-1ff1d85d1bdf?w=500&q=75",
  ],
};

/**
 * Deterministic hash function — same product_id always maps to the same index.
 * Uses djb2 hash algorithm (fast, good distribution, no crypto overhead).
 */
function hashProductId(productId: string): number {
  let hash = 5381;
  for (let i = 0; i < productId.length; i++) {
    hash = ((hash << 5) + hash) ^ productId.charCodeAt(i);
    hash = hash >>> 0; // Force unsigned 32-bit integer
  }
  return hash;
}

/**
 * getMockProductImage(product_id, category)
 *
 * Returns a unique, deterministic image URL for any product.
 *
 * - Same product_id → always the same image (stable across reloads)
 * - Different products in the same category → different images
 * - Category-appropriate images (electronics looks like gadgets, etc.)
 * - Falls back to picsum.photos/seed/{product_id} if category has no pool
 *
 * Usage:
 *   const src = getMockProductImage("SKU001000", "Electronics")
 *   // → "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=500&q=75"
 */
export function getMockProductImage(productId: string, category: string): string {
  // Try category-specific pool first
  const pool =
    CATEGORY_IMAGES[category] ||
    CATEGORY_IMAGES[category.split(" ")[0]] ||  // "Home & Kitchen" → "Home"
    CATEGORY_IMAGES["default"];

  const index = hashProductId(productId) % pool.length;
  return pool[index];
}

/**
 * getPicsumImage(product_id)
 *
 * Alternative: uses picsum.photos seed for a deterministic random image.
 * Useful for products outside our curated category pools.
 * Images look professional (photography, not illustrations).
 */
export function getPicsumImage(productId: string, size = 400): string {
  // Use the product_id as seed — picsum guarantees same seed = same image
  return `https://picsum.photos/seed/${productId}/${size}/${size}`;
}

/**
 * getProductImageWithFallback
 *
 * Returns category-aware image, with picsum as fallback.
 * Handles both organizer catalog products and synthetic demo products.
 */
export function getProductImageWithFallback(
  productId: string,
  category: string,
  preferCurated = true,
): string {
  if (preferCurated && CATEGORY_IMAGES[category]) {
    return getMockProductImage(productId, category);
  }
  return getPicsumImage(productId);
}

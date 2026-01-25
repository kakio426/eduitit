
import os
import time

file_path = r'c:\Users\kakio\eduitit\core\templates\core\includes\card_product.html'

content = """<div class="{% if product.card_size == 'hero' %}md:col-span-2 md:row-span-2{% elif product.card_size == 'wide' %}md:col-span-2{% elif product.card_size == 'tall' %}md:row-span-2{% endif %}"
    data-aos="fade-up" data-aos-delay="{{ delay|default:'100' }}">
    <div class="clay-card p-6 md:p-8 h-full relative overflow-hidden group cursor-pointer card-{{ product.color_theme }} product-card bg-white/60 backdrop-blur-sm"
        role="button" tabindex="0" data-product-id="{{ product.id }}">
        
        <div class="relative z-10 flex flex-col h-full justify-between">
            <div>
                <div class="flex justify-between items-start mb-4">
                    <div class="icon-box theme-icon {% if product.card_size == 'hero' %}scale-110{% endif %}">
                        {% if "fa-" in product.icon %}<i class="{{ product.icon }}"></i>{% else %}{{ product.icon }}{% endif %}
                    </div>
                    {% if product.card_size == 'hero' %}
                    <span class="px-3 py-1 theme-badge rounded-full text-xs font-bold uppercase tracking-wider">Featured</span>
                    {% endif %}
                </div>

                <div>
                    <span class="text-xs font-bold tracking-widest uppercase text-gray-400 mb-2 block">{{ product.service_type|title }}</span>
                    <h3 class="{% if product.card_size == 'hero' %}text-3xl lg:text-4xl{% else %}text-xl lg:text-2xl{% endif %} font-bold text-gray-800 leading-tight mb-3 group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-gray-800 group-hover:to-gray-500 transition-all">
                        {{ product.title }}
                    </h3>
                    <p class="{% if product.card_size == 'hero' %}text-lg md:text-xl{% else %}text-base md:text-lg{% endif %} text-gray-500 font-hand leading-relaxed">
                        {% if product.card_size == 'hero' %}
                        {{ product.lead_text|default:product.description|truncatechars:120 }}
                        {% else %}
                        {{ product.lead_text|default:product.description|truncatechars:60 }}
                        {% endif %}
                    </p>
                </div>
            </div>

            <div class="mt-6 flex items-center justify-between">
                <div class="flex items-center gap-2 font-semibold text-gray-400 group-hover:text-gray-700 transition-colors">
                    <span class="text-sm">자세히 보기</span>
                    <i class="fa-solid fa-arrow-right text-xs group-hover:translate-x-1 transition-transform"></i>
                </div>
                {% if product.card_size == 'hero' %}
                <div class="w-10 h-10 rounded-full bg-gray-800 text-white flex items-center justify-center text-sm shadow-lg group-hover:bg-purple-600 group-hover:rotate-45 transition-all duration-500">
                    <i class="fa-solid fa-plus"></i>
                </div>
                {% endif %}
            </div>
        </div>

        <!-- Subtle Background Decorative Shape -->
        <div class="absolute -bottom-6 -right-6 w-20 h-20 rounded-full bg-current opacity-[0.03] group-hover:scale-150 transition-transform duration-700"></div>
    </div>
</div>"""

try:
    if os.path.exists(file_path):
        os.remove(file_path)
        print("Deleted existing file.")
        time.sleep(1) # Wait for filesystem
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Created new file with correct content.")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        read_back = f.read()
        print("Read back content length:", len(read_back))
        # Simple verification check
        if "{% if" in read_back and "{% endif %}" in read_back:
            print("Verification: Tags look present.")
        else:
            print("Verification: Tags missing??")

except Exception as e:
    print(f"Error: {e}")

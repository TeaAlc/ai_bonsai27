// Minimal reproduction of the pinned llama-model.cpp device-split calculation.
// It isolates the index error; it does not simulate CUDA memory availability.
#include <algorithm>
#include <cmath>
#include <iostream>
#include <vector>

int main() {
    for (float initial : {0.0f, 1.0f}) {
        std::vector<float> splits{initial};
        std::vector<int> devices{0};
        const float sum = initial;
        splits[0] /= sum;
        const auto index = std::upper_bound(splits.begin(), splits.end(), 0.0f) - splits.begin();
        std::cout << "split=" << initial << " normalized=" << splits[0]
                  << " index=" << index;
        try {
            std::cout << " device=" << devices.at(index) << '\n';
        } catch (const std::out_of_range& error) {
            std::cout << " exception=" << error.what() << '\n';
        }
    }
}
